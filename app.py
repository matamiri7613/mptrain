from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import json
import os
import time
import uuid
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Required for session management and flash messages

# User database with updated roles - removed admin user
users = {
    'user1': {
        'password': 'user123',
        'role': 'primary_reviewer'
    },
    'user2': {
        'password': 'user456',
        'role': 'submitter'
    },
    'newreviewer': {
        'password': 'newpass123',
        'role': 'secondary_reviewer'
    }
}

# Store notifications in memory (could be moved to a persistent storage in production)
notifications = {}

# Store new results state
new_results = {}

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username in users and users[username]['password'] == password:
            # Store user information in session
            session['username'] = username
            session['role'] = users[username]['role']
            flash('ورود با موفقیت انجام شد', 'success')
            return redirect(url_for('index'))
        else:
            flash('نام کاربری و یا رمز صحیح نمی‌باشد', 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('شما از سیستم خارج شدید', 'info')
    return redirect(url_for('login'))

@app.route('/index')
def index():
    if 'username' not in session:
        flash('لطفا ابتدا وارد شوید', 'error')
        return redirect(url_for('login'))
    
    user_role = session.get('role')
    username = session.get('username')
    
    # Check if there are any notifications for the user
    user_notifications = notifications.get(username, [])
    
    return render_template('index.html', user_role=user_role, notifications=user_notifications)

@app.route('/picture_and_table')
def picture_and_table():
    if 'username' not in session:
        flash('لطفا ابتدا وارد شوید', 'error')
        return redirect(url_for('login'))
    
    return render_template('picture_and_table.html')

@app.route('/picture_and_table_se')
def picture_and_table_se():
    if 'username' not in session:
        flash('لطفا ابتدا وارد شوید', 'error')
        return redirect(url_for('login'))
    
    return render_template('picture_and_table_se.html')

@app.route('/picture_and_table_de')
def picture_and_table_de():
    if 'username' not in session:
        flash('لطفا ابتدا وارد شوید', 'error')
        return redirect(url_for('login'))
    
    return render_template('picture_and_table_de.html')

@app.route('/save_numbers', methods=['POST'])
def save_numbers():
    if 'username' not in session:
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401
    
    # Only submitter users can submit data
    if session['role'] != 'submitter':
        return jsonify({'status': 'error', 'message': 'Only submitters can submit data'}), 403
    
    try:
        data = request.get_json()
        print("Received data:", data)  

        if not data:
            return jsonify({'status': 'error', 'message': 'No data received'}), 400

        A = data.get('A')
        B = data.get('B')
        C = data.get('C')
        D = data.get('D')
        E = data.get('E')
        manufacturer = data.get('manufacturer')
        date = data.get('date')
        currentDateTime = data.get('currentDateTime')
        
        # Add username of who submitted the data
        submitter = session['username']
        # Default primary reviewer is user1
        primary_reviewer = 'user1'

        if not all([A, B, C, D, E, manufacturer, date, currentDateTime]):
            return jsonify({'status': 'error', 'message': 'Missing data'}), 400

        new_entry = {
            'id': str(uuid.uuid4()),
            'A': A, 
            'B': B, 
            'C': C, 
            'D': D, 
            'E': E, 
            'manufacturer': manufacturer, 
            'date': date, 
            'currentDateTime': currentDateTime,
            'submitter': submitter,
            'primary_reviewer': primary_reviewer,
            'secondary_reviewer': 'newreviewer',
            'review_stage': 'initial',  # New workflow stages: initial, with_secondary, pending_final, completed
            'primary_review_status': None,
            'acknowledged': False,  # For the secondary reviewer to acknowledge receipt
            'final_decision': None,
            'primary_reviewer_comment': '',
            'final_comment': '',
            'submission_timestamp': int(time.time()),
            'secondary_reviewer_data': None  # New field for additional data from secondary reviewer
        }

        # Read existing data (handle file errors)
        try:
            with open('saved_numbers.json', 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
                
                # Add IDs to existing entries if they don't have one
                for entry in existing_data:
                    if 'id' not in entry:
                        entry['id'] = str(uuid.uuid4())
        except (FileNotFoundError, json.JSONDecodeError):
            existing_data = []

        # Append new entry and save
        existing_data.append(new_entry)

        with open('saved_numbers.json', 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=4)
            
        # Create notification for primary reviewer
        if primary_reviewer not in notifications:
            notifications[primary_reviewer] = []
            
        notifications[primary_reviewer].append({
            'id': new_entry['id'],
            'message': f'New data submission from {submitter} needs initial review',
            'timestamp': int(time.time()),
            'read': False
        })

        return jsonify({'status': 'success', 'message': 'Data saved successfully and sent to user1 for initial review!'})

    except Exception as e:
        print("Error:", e)
        return jsonify({'status': 'error', 'message': f'Internal Server Error: {str(e)}'}), 500

@app.route('/view_saved_numbers', methods=['GET'])
def view_saved_numbers():
    if 'username' not in session:
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401
    
    try:
        # Read the saved data
        with open('saved_numbers.json', 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
            
            # Add IDs to existing entries if they don't have one
            for entry in existing_data:
                if 'id' not in entry:
                    entry['id'] = str(uuid.uuid4())
        
        current_user = session['username']
        user_role = session['role']
        
        filtered_data = []
        
        # Filter data based on user role
        if user_role == 'primary_reviewer':
            # Primary reviewer (user1) sees entries addressed to them
            filtered_data = [entry for entry in existing_data if entry.get('primary_reviewer') == current_user]
        elif user_role == 'secondary_reviewer':
            # Secondary reviewer sees entries that need their acknowledgment
            filtered_data = [entry for entry in existing_data if entry.get('secondary_reviewer') == current_user 
                             and entry.get('review_stage') == 'with_secondary']
        elif user_role == 'submitter':
            # Submitter sees their own submissions
            filtered_data = [entry for entry in existing_data if entry.get('submitter') == current_user]
        
        # Return the filtered data as a JSON response
        return jsonify(filtered_data), 200
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading file: {e}")
        return jsonify({'status': 'error', 'message': 'Unable to retrieve saved data'}), 500

@app.route('/reviewer/dashboard')
def reviewer_dashboard():
    if 'username' not in session or session['role'] not in ['primary_reviewer', 'secondary_reviewer']:
        flash('شما دسترسی لازم را ندارید', 'error')
        return redirect(url_for('index'))
    
    user_role = session.get('role')
    
    if user_role == 'primary_reviewer':
        return render_template('primary_reviewer_dashboard.html')
    else:
        return render_template('secondary_reviewer_dashboard.html')

@app.route('/submitter/dashboard')
def submitter_dashboard():
    if 'username' not in session or session['role'] != 'submitter':
        flash('شما دسترسی لازم را ندارید', 'error')
        return redirect(url_for('index'))
    
    return render_template('submitter_dashboard.html')

@app.route('/reviewer/review_submissions', methods=['GET'])
def review_submissions():
    if 'username' not in session or session['role'] not in ['primary_reviewer', 'secondary_reviewer']:
        return jsonify({'status': 'error', 'message': 'Unauthorized access'}), 403
    
    try:
        # Read the saved data
        with open('saved_numbers.json', 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
        
        current_user = session['username']
        user_role = session['role']
        
        filtered_data = []
        
        # Filter data based on user role and new workflow stages
        if user_role == 'primary_reviewer':
            # Primary reviewer sees entries in initial, pending_final, or completed stage
            filtered_data = [entry for entry in existing_data 
                            if entry.get('primary_reviewer') == current_user]
        elif user_role == 'secondary_reviewer':
            # Secondary reviewer only sees entries that need their acknowledgment
            filtered_data = [entry for entry in existing_data 
                            if entry.get('review_stage') == 'with_secondary' and entry.get('secondary_reviewer') == current_user]
        
        # Sort by submission timestamp (newest first) and review stage
        filtered_data.sort(key=lambda x: (x.get('review_stage', 'initial'), -x.get('submission_timestamp', 0)))
        
        # Return the filtered data as a JSON response
        return jsonify(filtered_data), 200
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading file: {e}")
        if isinstance(e, FileNotFoundError):
            # Create an empty file if it doesn't exist
            with open('saved_numbers.json', 'w', encoding='utf-8') as f:
                json.dump([], f)
            return jsonify([]), 200
        return jsonify({'status': 'error', 'message': 'Unable to retrieve saved data'}), 500

# New route for sending to secondary reviewer
@app.route('/reviewer/send_to_secondary/<submission_id>', methods=['POST'])
def send_to_secondary(submission_id):
    """Send submission to secondary reviewer for acknowledgment."""
    if 'username' not in session or session['role'] != 'primary_reviewer':
        return jsonify({'status': 'error', 'message': 'Unauthorized access'}), 403
    
    try:
        data = request.json
        comment = data.get('comment', '')
        timestamp = data.get('timestamp', int(time.time()))
        
        # Read existing data
        with open('saved_numbers.json', 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
        
        # Find the submission in the data
        entry_found = False
        for entry in existing_data:
            if entry.get('id') == submission_id:
                current_user = session['username']
                
                # Check if user is allowed to review this entry
                if entry.get('primary_reviewer') != current_user:
                    return jsonify({'status': 'error', 'message': 'You are not authorized to review this submission'}), 403
                
                # Update submission status
                entry['review_stage'] = 'with_secondary'
                entry['primary_reviewer_comment'] = comment
                entry['sent_to_secondary_timestamp'] = timestamp
                entry['primary_review_status'] = True  # Mark as approved by primary
                
                # Notify secondary reviewer
                secondary_reviewer = entry.get('secondary_reviewer')
                if secondary_reviewer not in notifications:
                    notifications[secondary_reviewer] = []
                
                notifications[secondary_reviewer].append({
                    'id': submission_id,
                    'message': f'New data from {entry.get("submitter")} needs your acknowledgment and additional data',
                    'timestamp': int(time.time()),
                    'read': False
                })
                
                entry_found = True
                break
        
        if not entry_found:
            return jsonify({'status': 'error', 'message': 'Submission not found'}), 404
        
        # Save back to file (atomic write)
        temp_file = 'saved_numbers_temp.json'
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=4)
        
        # Replace original file (ensures no corruption)
        os.replace(temp_file, 'saved_numbers.json')
        
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        print(f"Error in send_to_secondary: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# New route for rejecting submission directly
@app.route('/reviewer/reject_submission/<submission_id>', methods=['POST'])
def reject_submission(submission_id):
    """Reject submission at initial review stage."""
    if 'username' not in session or session['role'] != 'primary_reviewer':
        return jsonify({'status': 'error', 'message': 'Unauthorized access'}), 403
    
    try:
        data = request.json
        comment = data.get('comment', '')
        timestamp = data.get('timestamp', int(time.time()))
        
        # Read existing data
        with open('saved_numbers.json', 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
        
        # Find the submission in the data
        entry_found = False
        for entry in existing_data:
            if entry.get('id') == submission_id:
                current_user = session['username']
                
                # Check if user is allowed to review this entry
                if entry.get('primary_reviewer') != current_user:
                    return jsonify({'status': 'error', 'message': 'You are not authorized to review this submission'}), 403
                
                # Update submission status
                entry['review_stage'] = 'completed'
                entry['primary_reviewer_comment'] = comment
                entry['final_decision'] = False
                entry['final_decision_timestamp'] = timestamp
                entry['final_comment'] = comment
                entry['primary_review_status'] = False  # Mark as rejected by primary
                
                # Mark this as a new result for the submitter
                submitter = entry.get('submitter')
                if submitter not in new_results:
                    new_results[submitter] = []
                    
                new_results[submitter].append(submission_id)
                
                # Notify submitter of rejection
                if submitter not in notifications:
                    notifications[submitter] = []
                
                notifications[submitter].append({
                    'id': submission_id,
                    'message': f'Your submission has been rejected: {comment}',
                    'timestamp': int(time.time()),
                    'read': False
                })
                
                entry_found = True
                break
        
        if not entry_found:
            return jsonify({'status': 'error', 'message': 'Submission not found'}), 404
        
        # Save back to file (atomic write)
        temp_file = 'saved_numbers_temp.json'
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=4)
        
        # Replace original file (ensures no corruption)
        os.replace(temp_file, 'saved_numbers.json')
        
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        print(f"Error in reject_submission: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Updated route for secondary reviewer to acknowledge submission and provide additional data
@app.route('/reviewer/acknowledge_submission/<submission_id>', methods=['POST'])
def acknowledge_submission(submission_id):
    """Secondary reviewer acknowledges receipt and provides additional data."""
    if 'username' not in session or session['role'] != 'secondary_reviewer':
        return jsonify({'status': 'error', 'message': 'Unauthorized access'}), 403
    
    try:
        data = request.json
        timestamp = data.get('timestamp', int(time.time()))
        additional_data = data.get('additional_data', {})
        
        # Validate that required additional data is provided
        if not additional_data or not all(k in additional_data for k in ['quality_check', 'packaging_status', 'production_line', 'verification_code']):
            return jsonify({'status': 'error', 'message': 'Missing required additional data fields'}), 400
        
        # Read existing data
        with open('saved_numbers.json', 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
        
        # Find the submission in the data
        entry_found = False
        for entry in existing_data:
            if entry.get('id') == submission_id:
                current_user = session['username']
                
                # Check if user is allowed to acknowledge this entry
                if entry.get('secondary_reviewer') != current_user:
                    return jsonify({'status': 'error', 'message': 'You are not authorized to acknowledge this submission'}), 403
                
                # Update submission status and add the additional data
                entry['review_stage'] = 'pending_final'
                entry['acknowledged'] = True
                entry['acknowledged_timestamp'] = timestamp
                entry['secondary_reviewer_data'] = additional_data
                
                # Notify primary reviewer for final decision
                primary_reviewer = entry.get('primary_reviewer')
                if primary_reviewer not in notifications:
                    notifications[primary_reviewer] = []
                
                notifications[primary_reviewer].append({
                    'id': submission_id,
                    'message': f'Secondary reviewer has acknowledged receipt and provided additional data for submission from {entry.get("submitter")}. Final decision needed.',
                    'timestamp': int(time.time()),
                    'read': False
                })
                
                entry_found = True
                break
        
        if not entry_found:
            return jsonify({'status': 'error', 'message': 'Submission not found'}), 404
        
        # Save back to file (atomic write)
        temp_file = 'saved_numbers_temp.json'
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=4)
        
        # Replace original file (ensures no corruption)
        os.replace(temp_file, 'saved_numbers.json')
        
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        print(f"Error in acknowledge_submission: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Updated route for primary reviewer to make final decision
@app.route('/reviewer/make_final_decision/<submission_id>', methods=['POST'])
def make_final_decision(submission_id):
    """Primary reviewer makes final decision after secondary reviewer acknowledgment and data submission."""
    if 'username' not in session or session['role'] != 'primary_reviewer':
        return jsonify({'status': 'error', 'message': 'Unauthorized access'}), 403
    
    try:
        data = request.json
        approved = data.get('approved', False)
        comment = data.get('comment', '')
        timestamp = data.get('timestamp', int(time.time()))
        include_secondary_data = data.get('include_secondary_data', False)  # Default to not including secondary data
        
        # Read existing data
        with open('saved_numbers.json', 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
        
        # Find the submission in the data
        entry_found = False
        for entry in existing_data:
            if entry.get('id') == submission_id:
                current_user = session['username']
                
                # Check if user is allowed to make decision on this entry
                if entry.get('primary_reviewer') != current_user:
                    return jsonify({'status': 'error', 'message': 'You are not authorized to make decisions on this submission'}), 403
                
                # Check if secondary reviewer has provided the required additional data
                if not entry.get('secondary_reviewer_data'):
                    return jsonify({'status': 'error', 'message': 'Cannot make final decision: Secondary reviewer has not provided required additional data'}), 400
                
                # Update submission status
                entry['review_stage'] = 'completed'
                entry['final_decision'] = approved
                entry['final_comment'] = comment
                entry['final_decision_timestamp'] = timestamp
                
                # Create a copy of the entry for the submitter notification, excluding secondary data if needed
                submitter_entry = entry.copy()
                if not include_secondary_data:
                    # Create a clean copy without the secondary reviewer data for the submitter
                    submitter_entry['secondary_reviewer_data'] = None
                
                # Mark this as a new result for the submitter
                submitter = entry.get('submitter')
                if submitter not in new_results:
                    new_results[submitter] = []
                    
                new_results[submitter].append(submission_id)
                
                # Notify submitter of final decision
                if submitter not in notifications:
                    notifications[submitter] = []
                
                status = "approved" if approved else "rejected"
                notifications[submitter].append({
                    'id': submission_id,
                    'message': f'Your submission has been {status}: {comment}',
                    'timestamp': int(time.time()),
                    'read': False
                })
                
                entry_found = True
                break
        
        if not entry_found:
            return jsonify({'status': 'error', 'message': 'Submission not found'}), 404
        
        # Save back to file (atomic write)
        temp_file = 'saved_numbers_temp.json'
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=4)
        
        # Replace original file (ensures no corruption)
        os.replace(temp_file, 'saved_numbers.json')
        
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        print(f"Error in make_final_decision: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
# Keep the existing process_submission route for backward compatibility
@app.route('/reviewer/process_submission/<string:submission_id>', methods=['POST'])
def process_submission(submission_id):
    if 'username' not in session or session['role'] not in ['primary_reviewer', 'secondary_reviewer']:
        return jsonify({'status': 'error', 'message': 'Unauthorized access'}), 403
    
    try:
        # Get approval decision and comment
        data = request.get_json()
        is_approved = data.get('approved', False)
        comment = data.get('comment', '')
        
        # Read existing data
        with open('saved_numbers.json', 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
        
        # Find entry by ID
        entry_found = False
        submitter = None
        
        for entry in existing_data:
            if entry.get('id') == submission_id:
                current_user = session['username']
                user_role = session['role']
                review_stage = entry.get('review_stage', 'initial')
                
                # Check if user is allowed to review this entry
                if (user_role == 'primary_reviewer' and entry.get('primary_reviewer') != current_user) or \
                   (user_role == 'secondary_reviewer' and entry.get('secondary_reviewer') != current_user):
                    return jsonify({'status': 'error', 'message': 'You are not authorized to review this submission'}), 403
                
                # Process based on review stage and role - use new endpoints instead for most workflows
                if user_role == 'primary_reviewer' and review_stage == 'initial':
                    # Redirect to new endpoints
                    if is_approved:
                        return send_to_secondary(submission_id)
                    else:
                        return reject_submission(submission_id)
                
                elif user_role == 'secondary_reviewer' and review_stage == 'with_secondary':
                    # Use acknowledge_submission instead
                    return acknowledge_submission(submission_id)
                
                elif user_role == 'primary_reviewer' and review_stage == 'pending_final':
                    # Use make_final_decision instead
                    return make_final_decision(submission_id)
                
                entry_found = True
                break
                
        if not entry_found:
            return jsonify({'status': 'error', 'message': 'Submission not found'}), 404
        
        # This endpoint is now primarily for backward compatibility
        return jsonify({
            'status': 'success',
            'message': 'Submission processed successfully (legacy endpoint)'
        }), 200
        
    except Exception as e:
        print(f"Error in process_submission: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/notifications', methods=['GET'])
def get_notifications():
    if 'username' not in session:
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401
    
    username = session['username']
    user_notifications = notifications.get(username, [])
    
    return jsonify(user_notifications), 200

@app.route('/notifications/mark_read/<string:notification_id>', methods=['POST'])
def mark_notification_read(notification_id):
    if 'username' not in session:
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401
    
    username = session['username']
    
    if username in notifications:
        for notification in notifications[username]:
            if notification.get('id') == notification_id:
                notification['read'] = True
                return jsonify({'status': 'success'}), 200
    
    return jsonify({'status': 'error', 'message': 'Notification not found'}), 404

# Submitter dashboard routes

@app.route('/view_user_data/<string:username>', methods=['GET'])
def view_user_data(username):
    if 'username' not in session:
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401
    
    try:
        # Read the saved data
        try:
            with open('saved_numbers.json', 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            existing_data = []
        
        # Filter data based on the requested user
        current_submitter = session['username']
        
        # Filter submissions made by the current submitter
        submitter_data = [entry for entry in existing_data if entry.get('submitter') == current_submitter]
        
        # Further filter based on the requested viewer
        filtered_data = []
        
        if username == 'user1':
            # Show data reviewed by primary reviewer
            filtered_data = [
                {
                    'A': entry.get('A'),
                    'B': entry.get('B'),
                    'C': entry.get('C'),
                    'D': entry.get('D'),
                    'E': entry.get('E'),
                    'manufacturer': entry.get('manufacturer'),
                    'date': entry.get('date'),
                    'submission_timestamp': entry.get('submission_timestamp'),
                    'review_status': 'approved' if entry.get('primary_review_status') else 
                                   ('rejected' if entry.get('primary_review_status') is False else 
                                   ('in_secondary_review' if entry.get('review_stage') == 'with_secondary' else 'pending')),
                    'primary_review_completed': entry.get('primary_review_status') is not None,
                    'final_decision_made': entry.get('final_decision') is not None,
                    'approved': entry.get('final_decision')
                }
                for entry in submitter_data
            ]
        elif username == 'newreviewer':
            # Show data acknowledged by secondary reviewer
            filtered_data = [
                {
                    'A': entry.get('A'),
                    'B': entry.get('B'),
                    'C': entry.get('C'),
                    'D': entry.get('D'),
                    'E': entry.get('E'),
                    'manufacturer': entry.get('manufacturer'),
                    'date': entry.get('date'),
                    'submission_timestamp': entry.get('submission_timestamp'),
                    'review_status': 'acknowledged' if entry.get('acknowledged') else 'pending',
                    'acknowledged': entry.get('acknowledged') is True,
                    'additional_data': entry.get('secondary_reviewer_data')
                }
                for entry in submitter_data if entry.get('review_stage') in ['with_secondary', 'pending_final', 'completed']
            ]
        
        return jsonify(filtered_data), 200
    
    except Exception as e:
        print(f"Error retrieving user approval data: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/approval_summary', methods=['GET'])
def approval_summary():
    if 'username' not in session:
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401
    
    try:
        # Read the saved data
        try:
            with open('saved_numbers.json', 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            existing_data = []
        
        current_submitter = session['username']
        
        # Filter submissions made by the current submitter
        submitter_data = [entry for entry in existing_data if entry.get('submitter') == current_submitter]
        
        # Initialize counters
        user1_summary = {'approved': 0, 'rejected': 0, 'pending': 0}
        newreviewer_summary = {'acknowledged': 0, 'pending': 0, 'with_data': 0}
        
        # Count for user1 (primary reviewer)
        for entry in submitter_data:
            if entry.get('review_stage') == 'completed' and entry.get('final_decision') is True:
                user1_summary['approved'] += 1
            elif entry.get('review_stage') == 'completed' and entry.get('final_decision') is False:
                user1_summary['rejected'] += 1
            else:
                user1_summary['pending'] += 1
        
        # Count for newreviewer (secondary reviewer)
        for entry in submitter_data:
            if entry.get('review_stage') in ['pending_final', 'completed'] and entry.get('acknowledged') is True:
                newreviewer_summary['acknowledged'] += 1
                if entry.get('secondary_reviewer_data'):
                    newreviewer_summary['with_data'] += 1
            elif entry.get('review_stage') == 'with_secondary':
                newreviewer_summary['pending'] += 1
        
        return jsonify({
            'user1': user1_summary,
            'newreviewer': newreviewer_summary
        }), 200
    
    except Exception as e:
        print(f"Error retrieving approval summary: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/user1_final_results', methods=['GET'])
def user1_final_results():
    if 'username' not in session:
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401
    
    try:
        # Read the saved data
        try:
            with open('saved_numbers.json', 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            existing_data = []
        
        current_submitter = session['username']
        user_role = session['role']
        
        # Get submissions that have received a final decision
        final_results = []
        
        for entry in existing_data:
            if (entry.get('submitter') == current_submitter and 
                entry.get('final_decision') is not None and 
                entry.get('review_stage') == 'completed'):
                
                # Check if this is a new result
                is_new = False
                if current_submitter in new_results and entry.get('id') in new_results[current_submitter]:
                    is_new = True
                
                # Only include secondary data if the current user is the primary reviewer
                secondary_data = {}
                has_secondary_data = False
                
                if user_role == 'primary_reviewer' and entry.get('secondary_reviewer_data'):
                    secondary_data = {
                        'quality_check': entry.get('secondary_reviewer_data').get('quality_check', ''),
                        'packaging_status': entry.get('secondary_reviewer_data').get('packaging_status', ''),
                        'production_line': entry.get('secondary_reviewer_data').get('production_line', ''),
                        'verification_code': entry.get('secondary_reviewer_data').get('verification_code', '')
                    }
                    has_secondary_data = True
                
                final_results.append({
                    'id': entry.get('id'),
                    'A': entry.get('A'),
                    'B': entry.get('B'),
                    'C': entry.get('C'),
                    'D': entry.get('D'),
                    'E': entry.get('E'),
                    'manufacturer': entry.get('manufacturer'),
                    'date': entry.get('date'),
                    'approved': entry.get('final_decision'),
                    'comment': entry.get('final_comment', ''),
                    'final_decision_timestamp': entry.get('final_decision_timestamp', int(time.time())),
                    'secondary_data': secondary_data,
                    'has_secondary_data': has_secondary_data,
                    'new': is_new
                })
        
        return jsonify(final_results), 200
    
    except Exception as e:
        print(f"Error retrieving final results: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500    
@app.route('/final_results')
def final_results():
    if 'username' not in session:
        flash('لطفا ابتدا وارد شوید', 'error')
        return redirect(url_for('login'))
    
    return render_template('final_results.html')

@app.route('/mark_results_seen', methods=['POST'])
def mark_results_seen():
    if 'username' not in session:
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401
    
    username = session['username']
    
    # Clear new results for this user
    if username in new_results:
        new_results[username] = []
    
    return jsonify({'status': 'success', 'message': 'Results marked as seen'}), 200


if __name__ == '__main__':
    app.run(debug=True)