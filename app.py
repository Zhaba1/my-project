from flask import Flask, render_template, request, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import random
import re

# Инициализация приложения Flask
app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cities.db'  # База данных SQLite
db = SQLAlchemy(app)

# === Модель для хранения городов ===
class City(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

# === Модель для хранения пользователей ===
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    games_played = db.Column(db.Integer, default=0)   # Сыграно игр
    longest_chain = db.Column(db.Integer, default=0)  # Самая длинная цепочка
    wins = db.Column(db.Integer, default=0)           # Победы

# === Функция для очистки названий городов от текста в скобках ===
def clean_city_name(city):
    return re.sub(r'\s*$$.*?$$', '', city).strip()

# === Функция инициализации базы данных ===
def init_db():
    with app.app_context():
        db.create_all()  # Создаём таблицы
        if not City.query.first():  # Если база пустая
            try:
                with open('cities.txt', 'r', encoding='utf-8') as file:
                    cities = [clean_city_name(line.strip()) for line in file if line.strip()]
                for city in cities:
                    db.session.add(City(name=city))
                db.session.commit()
                print(f"Добавлено {len(cities)} городов.")
            except FileNotFoundError:
                print("Файл cities.txt не найден. Убедитесь, что он находится в той же папке, что и app.py.")
            except Exception as e:
                print(f"Произошла ошибка: {e}")

# === Функция получения последней буквы с исключениями ===
def get_last_letter(city):
    exceptions = ['ь', 'ы', 'й']
    for letter in reversed(city.lower()):
        if letter.isalpha() and letter not in exceptions:
            return letter
    return city[-1]  # если все буквы исключения

# === Маршрут: Приветствие ===
@app.route('/welcome')
def welcome():
    return render_template('welcome.html')

# === Маршрут: Главная (перенаправляет на приветствие) ===
@app.route('/')
def index():
    return redirect(url_for('welcome'))

# === Маршрут: Игра ===
@app.route('/game', methods=['GET', 'POST'])
def game():
    if 'user_id' not in session:
        return redirect(url_for('welcome'))

    if 'used_cities' not in session:
        session['used_cities'] = []
        session['last_letter'] = None

    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        user_city = clean_city_name(request.form['city'].strip().lower())
        last_letter = session['last_letter']

        if user_city in session['used_cities']:
            return render_template('index.html',
                                   error='Этот город уже использован!',
                                   user=user,
                                   used_cities=session['used_cities'])

        if last_letter and user_city[0] != last_letter:
            return render_template('index.html',
                                   error=f'Город должен начинаться на "{last_letter}"!',
                                   user=user,
                                   used_cities=session['used_cities'])

        city = City.query.filter_by(name=user_city.capitalize()).first()
        if not city:
            return render_template('index.html',
                                   error='Такого города нет в базе!',
                                   user=user,
                                   used_cities=session['used_cities'])

        session['used_cities'].append(user_city)
        last_letter = get_last_letter(user_city)
        session['last_letter'] = last_letter

        bot_city = get_bot_city(last_letter)
        if bot_city:
            session['used_cities'].append(bot_city.lower())
            session['last_letter'] = get_last_letter(bot_city.lower())
            return render_template('index.html',
                                   message=f'Бот ответил: {bot_city}',
                                   user=user,
                                   used_cities=session['used_cities'])
        else:
            # Игрок победил
            user.games_played += 1
            user.wins += 1
            current_chain = len(session['used_cities'])
            if current_chain > user.longest_chain:
                user.longest_chain = current_chain
            db.session.commit()

            session.clear()
            return render_template('index.html',
                                   message='Вы победили! Бот не смог ответить.',
                                   user=user,
                                   used_cities=[])

    return render_template('index.html', user=user, used_cities=session.get('used_cities', []))

# === Выбор города для бота ===
def get_bot_city(letter):
    cities = City.query.filter(City.name.ilike(f'{letter.upper()}%')).all()
    available = [city.name.lower() for city in cities if city.name.lower() not in session['used_cities']]
    return random.choice(available).capitalize() if available else None

# === Маршрут: Сдаться ===
@app.route('/give_up', methods=['POST'])
def give_up():
    if 'user_id' not in session:
        return redirect(url_for('welcome'))

    user = User.query.get(session['user_id'])
    user.games_played += 1

    current_chain = len(session.get('used_cities', []))
    if current_chain > user.longest_chain:
        user.longest_chain = current_chain

    db.session.commit()
    session.pop('used_cities', None)
    session.pop('last_letter', None)

    return redirect(url_for('game'))

# === Маршрут: Начать заново ===
@app.route('/reset', methods=['GET'])
def reset():
    session.pop('used_cities', None)
    session.pop('last_letter', None)
    return redirect(url_for('game'))

# === Маршрут: Регистрация ===
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if not username or not password:
            return render_template('register.html', error='Пожалуйста, заполните все поля.')

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return render_template('register.html', error='Пользователь с таким именем уже существует.')

        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))

    return render_template('register.html')

# === Маршрут: Вход ===
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['user_id'] = user.id
            return redirect(url_for('game'))
        else:
            return render_template('login.html', error='Неверное имя пользователя или пароль.')
    return render_template('login.html')

# === Маршрут: Выход ===
@app.route('/logout', methods=['GET'])
def logout():
    session.clear()
    return redirect(url_for('welcome'))

# === Маршрут: Профиль пользователя ===
@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('welcome'))

    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('logout'))

    # Получаем топ игроков по разным категориям
    top_players_by_games = User.query.order_by(User.games_played.desc()).limit(5).all()
    top_players_by_longest_chain = User.query.order_by(User.longest_chain.desc()).limit(5).all()
    top_players_by_wins = User.query.order_by(User.wins.desc()).limit(5).all()

    return render_template('profile.html',
                           user=user,
                           top_players_by_games=top_players_by_games,
                           top_players_by_longest_chain=top_players_by_longest_chain,
                           top_players_by_wins=top_players_by_wins)

# === Запуск приложения ===
if __name__ == '__main__':
    init_db()  # Инициализация базы данных
    app.run(debug=True)