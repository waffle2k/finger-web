from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_httpauth import HTTPBasicAuth
from werkzeug.utils import secure_filename
import os
import subprocess
import shlex
import datetime
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# Initialize HTTP Basic Auth
auth = HTTPBasicAuth()

@auth.verify_password
def verify_password(username, password):
    """Verify basic authentication credentials against multiple users"""
    return (username in app.config['BASIC_AUTH_USERS'] and 
            app.config['BASIC_AUTH_USERS'][username] == password)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return ('.' in filename and 
            filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS'])

@app.route('/')
def index():
    """Home page route"""
    return render_template('index.html', title='Home')

@app.route('/finger', methods=['GET', 'POST'])
def finger():
    """Finger command route"""
    result = None
    error = None
    username = request.args.get('user', '') or request.form.get('username', '')
    
    if request.method == 'POST' or username:
        try:
            # Sanitize username input
            if username:
                # Allow alphanumeric characters, dots, hyphens, underscores, and @ symbol for email-style usernames
                if not all(c.isalnum() or c in '.-_@' for c in username):
                    error = "Invalid username format. Only alphanumeric characters, dots, hyphens, underscores, and @ symbol are allowed."
                else:
                    # Execute finger command with specific user
                    cmd = ['finger', username]
            else:
                # Execute finger command without user (show all logged in users)
                cmd = ['finger']
            
            if not error:
                # Execute the command safely
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
                else:
                    error = process.stderr or "Finger command failed."
                    
        except subprocess.TimeoutExpired:
            error = "Command timed out. Please try again."
        except FileNotFoundError:
            error = "Finger command not available on this system."
        except Exception as e:
            error = f"An error occurred: {str(e)}"
    
    return render_template('finger.html', title='Finger', result=result, error=error, username=username)

@app.route('/finger/<path:username>')
def finger_direct(username):
    """Direct finger command route with username in URL"""
    result = None
    error = None
    
    try:
        # Sanitize username input
        if username:
            # Allow alphanumeric characters, dots, hyphens, underscores, and @ symbol for email-style usernames
            if not all(c.isalnum() or c in '.-_@' for c in username):
                error = "Invalid username format. Only alphanumeric characters, dots, hyphens, underscores, and @ symbol are allowed."
            else:
                # Execute finger command with specific user
                cmd = ['finger', username]
                
                # Execute the command safely
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
                else:
                    error = process.stderr or "Finger command failed."
                    
    except subprocess.TimeoutExpired:
        error = "Command timed out. Please try again."
    except FileNotFoundError:
        error = "Finger command not available on this system."
    except Exception as e:
        error = f"An error occurred: {str(e)}"
    
    return render_template('finger.html', title=f'Finger - {username}', result=result, error=error, username=username)

@app.route('/api/hello')
def api_hello():
    """Simple JSON API endpoint"""
    return jsonify({
        'message': 'Hello from Flask API!',
        'status': 'success',
        'version': '1.0'
    })

@app.route('/api/info')
def api_info():
    """API info endpoint"""
    return jsonify({
        'app_name': 'Finger Web Flask App',
        'routes': [
            '/',
            '/finger',
            '/finger/<username>',
            '/api/hello',
            '/api/info',
            '/api/upload'
        ],
        'framework': 'Flask'
    })

@app.route('/api/upload', methods=['POST'])
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
