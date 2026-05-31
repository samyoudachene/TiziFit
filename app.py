from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import os
from translations import TRANSLATIONS

app = Flask(__name__)
app.secret_key = "super_secret_key" # Utilisé pour sécuriser les sessions

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fitness.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Config Mail CORRIGÉE
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
# On cherche le nom de la variable 'MAIL_USERNAME' définie sur Render
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
# On cherche le nom de la variable 'MAIL_PASSWORD' définie sur Render
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')

db = SQLAlchemy(app)
mail = Mail(app)

# Modèle de la Base de Données (Nettoyé des doublons)
class UserTracker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True)
    mot_de_passe = db.Column(db.String(200))
    numero = db.Column(db.String(20))
    genre = db.Column(db.String(20))
    poids = db.Column(db.Float)
    taille = db.Column(db.Float)
    age = db.Column(db.Integer)
    image_file = db.Column(db.String(100))
    description = db.Column(db.Text)
    
    pack_actuel = db.Column(db.String(50), default="Aucun pack actif")
    calories_consommees = db.Column(db.Integer, default=0)
    objectif_calories = db.Column(db.Integer, default=2500)
    
    # NOUVELLE COLONNE : LE PROGRAMME DU COACH
    programme_coach = db.Column(db.Text, default="Ton coach Samy analyse actuellement tes données. Ton programme sur-mesure apparaîtra ici très bientôt !")

    # NOUVELLE COLONNE POUR LE GRAPHIQUE
    historique_poids = db.Column(db.Text)
    
with app.app_context():
    db.create_all()
    
    
# --- GESTION DES LANGUES ---
@app.context_processor
def inject_translations():
    lang = session.get('lang', 'fr')
    return dict(t=TRANSLATIONS.get(lang, TRANSLATIONS['fr']), current_lang=lang)

@app.route('/set_lang/<lang>')
def set_lang(lang):
    if lang in TRANSLATIONS:
        session['lang'] = lang
    return redirect(request.referrer or url_for('home'))
    

@app.route('/')
def home():
    return render_template('index.html')

# -- MISE À JOUR DE LA ROUTE COACHING --
@app.route('/coaching', methods=['GET', 'POST'])
def coaching():
    if request.method == 'POST':
        pack_name = request.form.get('pack_name')
        
        if 'user_id' in session:
            user = UserTracker.query.get(session['user_id'])
            
            # On enregistre le pack choisi dans la base de données
            user.pack_actuel = pack_name
            db.session.commit()
            
            # Envoi du mail au coach...
            msg = Message(f"Choix de Formule : {pack_name}",
                          sender=app.config['MAIL_DEFAULT_SENDER'],
                          recipients=['samyoudachene@gmail.com'])
            msg.body = f"Le client connecté {user.nom} a validé la formule : {pack_name}."
            try:
                mail.send(msg)
                flash(f"Félicitations ! Votre abonnement au {pack_name} est activé.", "success")
            except Exception as e:
                print(f"Erreur d'envoi d'email: {e}") # Pour voir l'erreur dans les logs Render
                flash("Votre pack est activé sur votre espace.", "success")
            
            return redirect(url_for('track'))
        else:
            return redirect(url_for('inscription', pack=pack_name))
            
    return render_template('coaching.html')

# -- NOUVELLE ROUTE : AJOUTER DES CALORIES --
@app.route('/ajouter_calories', methods=['POST'])
def ajouter_calories():
    if 'user_id' in session:
        user = UserTracker.query.get(session['user_id'])
        calories_repas = request.form.get('calories', type=int)
        
        if calories_repas:
            user.calories_consommees += calories_repas
            db.session.commit()
            flash(f"{calories_repas} kcal ajoutées avec succès !", "success")
            
    return redirect(url_for('track'))

# -- NOUVELLE ROUTE : METTRE A JOUR LE POIDS --
@app.route('/maj_poids', methods=['POST'])
def maj_poids():
    if 'user_id' in session:
        user = UserTracker.query.get(session['user_id'])
        nouveau_poids = request.form.get('poids', type=float)

        if nouveau_poids:
            user.poids = nouveau_poids
            if user.historique_poids:
                user.historique_poids += f",{nouveau_poids}"
            else:
                user.historique_poids = str(nouveau_poids)

            db.session.commit()
            flash(f"Votre nouveau poids de {nouveau_poids} kg a été enregistré.", "success")

    return redirect(url_for('track'))


# MISE À JOUR DE L'INSCRIPTION
@app.route('/inscription', methods=['GET', 'POST'])
def inscription():
    if request.method == 'POST':
        nom = request.form.get('nom')
        email = request.form.get('email')
        password = request.form.get('password')
        numero = request.form.get('numero')
        genre = request.form.get('genre')
        poids = request.form.get('poids')
        taille = request.form.get('taille')
        age = request.form.get('age')
        description = request.form.get('description')
        pack_recupere = request.form.get('pack_hidden', 'Non spécifié')

        hashed_password = generate_password_hash(password)

        file = request.files['image']
        filename = ""
        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        if UserTracker.query.filter_by(email=email).first():
            flash("Cet email est déjà utilisé. Veuillez vous connecter.", "warning")
            return redirect(url_for('login'))

        nouvel_utilisateur = UserTracker(
            nom=nom, email=email, mot_de_passe=hashed_password, numero=numero, 
            genre=genre, poids=float(poids), taille=float(taille), age=int(age), 
            image_file=filename, description=description,
            historique_poids=str(poids)
        )
        db.session.add(nouvel_utilisateur)
        db.session.commit()

        # Connexion automatique
        session['user_id'] = nouvel_utilisateur.id

        # Envoi du mail au Coach
        msg = Message(f"Nouveau Client Inscrit - Pack : {pack_recupere}",
                      sender=app.config['MAIL_DEFAULT_SENDER'],
                      recipients=['samyoudachene@gmail.com'])
        msg.body = f"Nouveau client: {nom}\nPack choisi: {pack_recupere}\nPoids: {poids}kg\nObjectif: {description}"
        try:
            mail.send(msg)
        except Exception as e:
            print(f"Erreur d'envoi d'email: {e}") # Pour voir l'erreur dans les logs Render

        flash(f"Inscription réussie ! Bienvenue dans votre espace et merci d'avoir choisi le {pack_recupere}.", "success")
        return redirect(url_for('track'))

    return render_template('inscription.html')

# -- LA VRAIE PAGE DE CONNEXION --
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = UserTracker.query.filter_by(email=email).first()
        
        # Vérification de l'email et du mot de passe
        if user and check_password_hash(user.mot_de_passe, password):
            session['user_id'] = user.id 
            flash("Connexion réussie !", "success")
            return redirect(url_for('track'))
        else:
            flash("Email ou mot de passe incorrect.", "danger")

    return render_template('login.html')

# -- L'ESPACE PERSONNEL (TRACK) --
@app.route('/track')
def track():
    if 'user_id' not in session:
        flash("Veuillez vous connecter pour accéder à votre espace.", "warning")
        return redirect(url_for('login'))
    
    user = UserTracker.query.get(session['user_id'])
    
    if user is None:
        session.pop('user_id', None)
        return redirect(url_for('login'))
        
    return render_template('track.html', user=user)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/temoignage')
def temoignage():
    return render_template('temoignage.html')

@app.route('/trouver_salles')
def trouver_salles():
    return render_template('trouver_salles.html')

# -- DECONNEXION --
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash("Vous avez été déconnecté.", "info")
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
