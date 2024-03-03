import requests
from flask import Flask, render_template, request, flash, session, redirect, url_for, jsonify

import os
import firebase_admin
from firebase_admin import auth, db, credentials
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import google.generativeai as genai
from bs4 import BeautifulSoup

app = Flask(__name__)
app.secret_key = 'bytecrafters'

# Firebase configuration
firebaseConfig = {
    "apiKey": "AIzaSyDpcZOqJEq3bxXVwYdTsAYdNVZ6bdqLZCQ",
    "authDomain": "recipemagic-f7c54.firebaseapp.com",
    "databaseURL": "https://recipemagic-f7c54-default-rtdb.firebaseio.com",
    "projectId": "recipemagic-f7c54",
    "storageBucket": "recipemagic-f7c54.appspot.com",
    "messagingSenderId": "640483685071",
    "appId": "1:640483685071:web:271e350ffbdf883c177dba"
}

cred = credentials.Certificate('serviceAccountKey.json')
firebase_admin.initialize_app(cred, firebaseConfig)



def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash("You need to log in to access this page.", 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        if 'user' not in session:
            flash("You need to log in to access this page.", 'error')
            return redirect(url_for('login'))

        search_term = request.form['searchbar']
        search_option = request.form['searchOption']

        prompt_text = ""
        if search_option == "By Food Name":
            prompt_text = f"your indian masterchef you know every indian recipe so tell me how to make {search_term} responce start with food name at top then ingredients,instructions,tips"
        elif search_option == "By Ingredients":
            prompt_text = f"your indian masterchef you know every indian recipe so tell me how to make a dish using {search_term} as the primary ingredient responce start with food name at top than ingredients,instructions,tips"

        response = generate_recipe(prompt_text)
        generated_recipe = response.text

        session['generated_recipe'] = generated_recipe
        return redirect(url_for('results'))

    return render_template('index.html')


@app.route('/aboutus')
def aboutus():
    return render_template('aboutus.html')


@app.route('/contactus')
def contactus():
    return render_template('contactus.html')


@app.route('/results')
@login_required
def results():
    generated_recipe_text = session.get('generated_recipe')

    # Check if the generated recipe text is present
    if generated_recipe_text:
        # Parse the generated recipe text
        generated_recipe = parse_generated_recipe(generated_recipe_text)

        # Fetch food image based on the recipe
        food_name = generated_recipe['food_name']
        image_url = fetch_food_image(food_name)

        return render_template('results.html', generated_recipe=generated_recipe, image_url=image_url)
    else:
        # Redirect the user back to the home page
        flash("No recipe generated. Please try again.", 'error')
        return redirect(url_for('home'))


def parse_generated_recipe(generated_recipe_text):
    # Initialize variables for sections
    food_name = ""
    ingredients = ""
    instructions = ""
    tips = ""

    # Remove extra whitespace and special characters
    generated_recipe_text = generated_recipe_text.replace("", "").replace("\n\n", "\n").strip()

    # Split the generated recipe text into sections based on the keywords
    sections = generated_recipe_text.split("Instructions:")

    # Extract food name and ingredients
    if len(sections) > 1:
        food_name, ingredients_section = sections[0].split("Ingredients:")
        ingredients = ingredients_section.strip()

    # Extract instructions and tips
    if len(sections) > 1:
        instructions_and_tips = sections[1]
        if "Tips:" in instructions_and_tips:
            instructions, tips = instructions_and_tips.split("Tips:")
            tips = tips.strip()
        else:
            instructions = instructions_and_tips

    # Strip and split ingredients, instructions, and tips
    ingredients_list = [ingredient.strip("*") for ingredient in ingredients.split("\n")] if ingredients else []
    instructions_list = [step.strip("*").strip() for step in instructions.split("\n")] if instructions else []
    tips_list = [tip.strip("*").strip() for tip in tips.split("\n")] if tips else []

    return {
        "food_name": food_name.strip(),
        "ingredients": ingredients_list,
        "instructions": instructions_list,
        "tips": tips_list
    }
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'user' in session:
        return redirect(url_for('home'))

    if request.method == 'POST':
        name = request.form['Name']
        username = request.form['Username']
        email = request.form['Email']
        password = generate_password_hash(request.form['Password'])

        # Firebase user creation
        try:
            user = auth.create_user(
                email=email,
                password=password
            )
            session['user'] = user.uid  # Store user ID in session
            flash("Registration successful!", 'success')
            return redirect(url_for('home'))
        except auth.EmailExistsError:
            flash("Email already exists. Please choose a different one.", 'error')
        except Exception as e:  # Handle other potential errors
            flash(f"An error occurred: {e}", 'error')

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        return redirect(url_for('home'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        try:
            # Check if the email exists in Firebase
            user = auth.get_user_by_email(email)

            # Email exists, attempt to sign in
            try:
                user = auth.sign_in_with_email_and_password(email, password)
                session['user'] = user['localId']  # Store user ID in session
                flash("Login successful!", 'success')
                return redirect(url_for('home'))
            except firebase_admin.auth.FirebaseAuthError as e:
                error_code = e.error_code
                if error_code == 'weak-password':
                    flash("Password is too weak.", 'error')
                elif error_code == 'invalid-email':
                    flash("Invalid email address.", 'error')
                elif error_code == 'user-not-found':
                    flash("User not found.", 'error')
                elif error_code == 'wrong-password':  # Use 'wrong-password' for newer versions
                    flash("Incorrect password.", 'error')
                else:
                    # Handle other potential errors
                    flash(f"An error occurred: {e}", 'error')

        except Exception as e:  # Handle other potential errors
            flash(f"An error occurred: {e}", 'error')

    return render_template('login.html')





def generate_recipe(prompt_parts):
    genai.configure(api_key="AIzaSyB4TfXRrsBE3q7ZQCpJgAIoWZoCTH31lDE")

    generation_config = {
        "temperature": 0.9,
        "top_p": 1,
        "top_k": 1,
        "max_output_tokens": 2048,
    }

    safety_settings = [
        {
            "category": "HARM_CATEGORY_HARASSMENT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
        },
        {
            "category": "HARM_CATEGORY_HATE_SPEECH",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
        },
        {
            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
        },
        {
            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
        },
    ]

    model = genai.GenerativeModel(model_name="gemini-pro",
                                  generation_config=generation_config,
                                  safety_settings=safety_settings)

    response = model.generate_content(prompt_parts)

    return response


def fetch_food_image(food_name):
    search_query = f"{food_name} dish"
    url = f'https://www.google.co.in/search?q={search_query}&source=lnms&tbm=isch'

    # Fetch image tag from Google Images
    image_tag = get_image_tag_from_page(url)

    if image_tag:
        # Extract image URL from the image tag
        image_url = image_tag.get('src')
        return image_url

    # If no image found, return a placeholder image URL
    return "https://via.placeholder.com/400x300.png"


def get_image_tag_from_page(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    # Find all img tags
    img_tags = soup.find_all('img')

    # Return the first img tag
    return img_tags[5] if img_tags else None


@app.route('/logout')
@login_required
def logout():
    session.pop('user', None)
    flash("You have been logged out.", 'info')
    return redirect(url_for('home'))


if __name__ == "__main__":
    # Run the app
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
