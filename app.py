from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import os
import subprocess
import shlex
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

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
            '/api/info'
        ],
        'framework': 'Flask'
    })

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
