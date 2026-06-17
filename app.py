from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_httpauth import HTTPBasicAuth
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
import os
import subprocess
import shlex
import datetime
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# Trust the front-end nginx's X-Forwarded-For so the real client IP is used for
# logging and rate limiting. Without this the app only ever sees the Docker
# bridge gateway (172.20.0.1), so every client on the internet would share one
# rate-limit bucket and log line.
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=app.config['PROXY_FORWARDED_COUNT'],
    x_proto=1,
    x_host=1,
)

# Initialize HTTP Basic Auth
auth = HTTPBasicAuth()

# Per-client-IP rate limiting. The app only ever receives nginx cache *misses*
# (upstream caches 200s for 30s), so these limits throttle exactly the uncached
# finger-daemon lookups (e.g. username enumeration) without touching the cached
# hot path that legitimate Fediverse previews ride on.
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[l.strip() for l in app.config['RATELIMIT_DEFAULT'].split(';') if l.strip()],
    storage_uri=app.config['RATELIMIT_STORAGE_URI'],
    enabled=app.config['RATELIMIT_ENABLED'],
    headers_enabled=True,
)

@auth.verify_password
def verify_password(username, password):
    """Verify basic authentication credentials against multiple users"""
    return (username in app.config['BASIC_AUTH_USERS'] and 
            app.config['BASIC_AUTH_USERS'][username] == password)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return ('.' in filename and 
            filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS'])

def safe_decode_output(raw_output):
    """
    Safely decode subprocess output with fallback encoding strategies.
    
    Args:
        raw_output (bytes): Raw bytes output from subprocess
        
    Returns:
        str: Decoded string output
    """
    if isinstance(raw_output, str):
        return raw_output
    
    # List of encodings to try in order
    encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
    
    for encoding in encodings:
        try:
            return raw_output.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    
    # If all encodings fail, use utf-8 with error handling
    try:
        return raw_output.decode('utf-8', errors='replace')
    except Exception:
        # Last resort: convert to string representation
        return str(raw_output, errors='ignore')

def run_finger_command(cmd):
    """
    Execute finger command with robust encoding handling.
    
    Args:
        cmd (list): Command list to execute
        
    Returns:
        tuple: (success, result_or_error, is_error)
    """
    try:
        # First try with text=True (UTF-8 decoding)
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if process.returncode == 0:
            result = process.stdout
            if not result.strip():
                result = "No information available."
            return True, result, False
        else:
            error = process.stderr or "Finger command failed."
            return False, error, True
            
    except UnicodeDecodeError:
        # Handle UTF-8 decoding error by using binary mode
        try:
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=False,  # Get raw bytes
                timeout=10
            )
            
            if process.returncode == 0:
                result = safe_decode_output(process.stdout)
                if not result.strip():
                    result = "No information available."
                return True, result, False
            else:
                error = safe_decode_output(process.stderr) or "Finger command failed."
                return False, error, True
                
        except Exception as e:
            return False, f"Encoding error occurred: {str(e)}", True
            
    except subprocess.TimeoutExpired:
        return False, "Command timed out. Please try again.", True
    except FileNotFoundError:
        return False, "Finger command not available on this system.", True
    except Exception as e:
        return False, f"An error occurred: {str(e)}", True

@app.route('/')
@limiter.exempt
def index():
    """Home page route (exempt from limits; also serves the container healthcheck)"""
    return render_template('index.html', title='Home')

@app.route('/finger', methods=['GET', 'POST'])
@limiter.limit(lambda: app.config['RATELIMIT_FINGER'])
def finger():
    """Finger search form.

    Any submitted username is redirected to the canonical
    ``/finger/<username>`` path so the lookup happens on a cacheable URL with
    the search term in it — repeated searches for the same user are served from
    the nginx response cache instead of re-running the finger command. A bare
    ``/finger`` with no user shows the local system users (no daemon enumeration
    risk: it never takes external input).
    """
    username = (request.args.get('user', '')
                or request.args.get('username', '')
                or request.form.get('username', '')).strip()

    if username:
        # Send the search to the cacheable canonical path.
        return redirect(url_for('finger_direct', username=username))

    # No user supplied: list logged-in system users.
    result = None
    error = None
    success, output, is_error = run_finger_command(['finger'])
    if success:
        result = output
    else:
        error = output

    return render_template('finger.html', title='Finger', result=result, error=error, username=username)

@app.route('/finger/<path:username>')
@limiter.limit(lambda: app.config['RATELIMIT_FINGER'])
def finger_direct(username):
    """Direct finger command route with username in URL"""
    result = None
    error = None
    
    # Sanitize username input
    if username:
        # Allow alphanumeric characters, dots, hyphens, underscores, and @ symbol for email-style usernames
        if not all(c.isalnum() or c in '.-_@' for c in username):
            error = "Invalid username format. Only alphanumeric characters, dots, hyphens, underscores, and @ symbol are allowed."
            app.logger.warning("rejected invalid finger username %r from %s",
                               username, get_remote_address())
        else:
            # Execute finger command with specific user
            cmd = ['finger', username]

            # Execute the command with robust encoding handling
            success, output, is_error = run_finger_command(cmd)
            if success:
                result = output
            else:
                error = output
                app.logger.warning("finger lookup failed for %r from %s: %s",
                                   username, get_remote_address(), output.strip()[:200])

    return render_template('finger.html', title=f'Finger - {username}', result=result, error=error, username=username)

@app.route('/api/finger')
@app.route('/api/finger/<path:username>')
@limiter.limit(lambda: app.config['RATELIMIT_FINGER'])
def api_finger(username=None):
    """JSON API endpoint for finger queries"""
    if username is None:
        username = request.args.get('user', '')

    if username:
        if not all(c.isalnum() or c in '.-_@' for c in username):
            return jsonify({'error': 'Invalid username', 'status': 'error'}), 400
        cmd = ['finger', username]
    else:
        cmd = ['finger']

    success, output, is_error = run_finger_command(cmd)
    if success:
        return jsonify({'result': output, 'username': username, 'status': 'success'})
    return jsonify({'error': output, 'status': 'error'}), 500

@app.route('/api/info')
def api_info():
    """API info endpoint"""
    return jsonify({
        'app_name': 'finger-web',
        'routes': [
            '/',
            '/finger',
            '/finger/<username>',
            '/api/finger',
            '/api/finger/<username>',
            '/api/info',
            '/api/upload'
        ],
        'framework': 'Flask'
    })

@app.route('/api/upload', methods=['POST'])
@limiter.limit(lambda: app.config['RATELIMIT_UPLOAD'])
@auth.login_required
def upload_file():
    """File upload endpoint with basic authentication and SCP transfer"""
    try:
        # Extract authenticated username
        authenticated_user = auth.current_user()
        
        # Check if the post request has the file part
        if 'file' not in request.files:
            return jsonify({
                'error': 'No file part in the request',
                'status': 'error'
            }), 400
        
        file = request.files['file']
        
        # Check if user selected a file
        if file.filename == '':
            return jsonify({
                'error': 'No file selected',
                'status': 'error'
            }), 400
        
        # Check if file is allowed
        if not allowed_file(file.filename):
            return jsonify({
                'error': f'File type not allowed. Allowed types: {", ".join(app.config["ALLOWED_EXTENSIONS"])}',
                'status': 'error'
            }), 400
        
        if file:
            # Generate secure filename with timestamp
            original_filename = secure_filename(file.filename)
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{original_filename}"
            
            # Ensure upload directory exists
            upload_folder = app.config['UPLOAD_FOLDER']
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
            
            # Save file locally
            file_path = os.path.join(upload_folder, filename)
            file.save(file_path)
            
            # Get file info
            file_size = os.path.getsize(file_path)
            
            # Initialize response data
            response_data = {
                'message': 'File uploaded successfully',
                'status': 'success',
                'file_info': {
                    'original_filename': original_filename,
                    'saved_filename': filename,
                    'local_file_path': file_path,
                    'file_size': file_size,
                    'upload_time': datetime.datetime.now().isoformat()
                }
            }
            
            # SCP file to remote server if enabled
            if app.config['SCP_ENABLED']:
                try:
                    remote_file_path = os.path.join(app.config['REMOTE_PATH'], authenticated_user).replace('\\', '/')
                    scp_destination = f"{app.config['REMOTE_USER']}@{app.config['REMOTE_HOST']}:{remote_file_path}"
                    
                    # Build SCP command
                    scp_cmd = [
                        'scp',
                        '-P', str(app.config['REMOTE_PORT']),
                        '-o', 'StrictHostKeyChecking=no',
                        '-o', 'UserKnownHostsFile=/dev/null'
                    ]
                    
                    # Add private key if specified
                    if app.config['REMOTE_PRIVATE_KEY']:
                        scp_cmd.extend(['-i', app.config['REMOTE_PRIVATE_KEY']])
                    
                    # Add source and destination
                    scp_cmd.extend([file_path, scp_destination])
                    
                    # Execute SCP command
                    scp_process = subprocess.run(
                        scp_cmd,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    if scp_process.returncode == 0:
                        response_data['scp_info'] = {
                            'remote_host': app.config['REMOTE_HOST'],
                            'remote_path': remote_file_path,
                            'scp_status': 'success',
                            'scp_message': 'File successfully transferred to remote server'
                        }
                        response_data['message'] = 'File uploaded and transferred to remote server successfully'
                    else:
                        response_data['scp_info'] = {
                            'scp_status': 'failed',
                            'scp_error': scp_process.stderr or 'SCP transfer failed',
                            'scp_message': 'File uploaded locally but remote transfer failed'
                        }
                        response_data['message'] = 'File uploaded locally but remote transfer failed'
                        
                except subprocess.TimeoutExpired:
                    response_data['scp_info'] = {
                        'scp_status': 'timeout',
                        'scp_error': 'SCP transfer timed out',
                        'scp_message': 'File uploaded locally but remote transfer timed out'
                    }
                    response_data['message'] = 'File uploaded locally but remote transfer timed out'
                    
                except Exception as scp_error:
                    response_data['scp_info'] = {
                        'scp_status': 'error',
                        'scp_error': str(scp_error),
                        'scp_message': 'File uploaded locally but SCP failed'
                    }
                    response_data['message'] = 'File uploaded locally but SCP failed'
            else:
                response_data['scp_info'] = {
                    'scp_status': 'disabled',
                    'scp_message': 'SCP transfer is disabled'
                }
            
            return jsonify(response_data), 200
            
    except Exception as e:
        return jsonify({
            'error': f'Upload failed: {str(e)}',
            'status': 'error'
        }), 500

@app.errorhandler(429)
def ratelimit_handler(error):
    """Handle rate-limit (429) responses; JSON for the API, HTML otherwise"""
    app.logger.warning(
        "Rate limit exceeded for %s on %s (%s)",
        get_remote_address(), request.path, error.description,
    )
    if request.path.startswith('/api/'):
        return jsonify({
            'error': 'Rate limit exceeded',
            'detail': str(error.description),
            'status': 'error',
        }), 429
    return render_template('429.html', title='Too Many Requests',
                           detail=error.description), 429

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    return render_template('404.html', title='Page Not Found'), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return render_template('500.html', title='Server Error'), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
