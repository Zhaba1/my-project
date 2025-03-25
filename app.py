from flask import Flask, render_template, request, session, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
import random
import re

# Инициализация приложения Flask
app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cities.db'  # База данных SQLite
db = SQLAlchemy(app)

# Модель для хранения городов
class City(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

# Модель для хранения пользователей
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

# Функция для очистки названий городов от текста в скобках
def clean_city_name(city):
    return re.sub(r'\s*\(.*?\)', '', city).strip()

# Функция инициализации базы данных
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

# Страница приветствия
@app.route('/welcome')
def welcome():
    return render_template('welcome.html')

# Главная страница игры (всегда перенаправляет на приветственную страницу)
@app.route('/')
def index():
    return redirect(url_for('welcome'))

# Маршрут для игры
@app.route('/game', methods=['GET', 'POST'])
def game():
    # Проверяем, авторизован ли пользователь
    if 'user_id' not in session:
        return redirect(url_for('welcome'))

    # Инициализируем сессию для игры
    if 'used_cities' not in session:
        session['used_cities'] = []
        session['last_letter'] = None

    if request.method == 'POST':
        user_city = clean_city_name(request.form['city'].strip().lower())
        last_letter = session['last_letter']

        # Проверка на повторение городов
        if user_city in session['used_cities']:
            return render_template('index.html', error='Этот город уже использован!')

        # Проверка на соответствие последней букве
        if last_letter and user_city[0] != last_letter:
            return render_template('index.html', error=f'Город должен начинаться на "{last_letter}"!')

        # Проверка, есть ли город в базе
        city = City.query.filter_by(name=user_city.capitalize()).first()
        if not city:
            return render_template('index.html', error='Такого города нет в базе!')

        # Добавляем город в список использованных
        session['used_cities'].append(user_city)
        last_letter = get_last_letter(user_city)
        session['last_letter'] = last_letter

        # Ход бота
        bot_city = get_bot_city(last_letter)
        if bot_city:
            session['used_cities'].append(bot_city.lower())
            session['last_letter'] = get_last_letter(bot_city.lower())
            return render_template('index.html', 
                                   message=f'Бот ответил: {bot_city}',
                                   user_city=city.name,
                                   bot_city=bot_city,
                                   last_letter=session['last_letter'],
                                   used_cities=session['used_cities'])
        else:
            session.clear()
            return render_template('index.html', message='Вы победили! Бот не смог ответить.')

    return render_template('index.html', used_cities=session['used_cities'])

# Маршрут для сброса игры
@app.route('/reset', methods=['GET'])
def reset():
    # Очищаем только игровую сессию, но не выходим из аккаунта
    session.pop('used_cities', None)
    session.pop('last_letter', None)
    return redirect(url_for('game'))  # Перенаправляем на главную страницу

# Регистрация пользователя
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if not username or not password:
            flash('Пожалуйста, заполните все поля.')
            return redirect(url_for('register'))

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Пользователь с таким именем уже существует.')
            return redirect(url_for('register'))

        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        flash('Регистрация успешна. Теперь вы можете войти.')
        return redirect(url_for('login'))

    return render_template('register.html')

# Вход пользователя
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
            flash('Неверное имя пользователя или пароль.')
            return redirect(url_for('login'))

    return render_template('login.html')

# Выход пользователя
@app.route('/logout', methods=['GET'])
def logout():
    session.clear()  # Очищаем сессию
    return redirect(url_for('welcome'))  # Перенаправляем на приветственную страницу

# Функция получения последней буквы города
def get_last_letter(city):
    last_letter = city[-1]
    if last_letter in ['ь', 'ы', 'ъ']:
        return city[-2]
    return last_letter

# Выбор города для бота
def get_bot_city(letter):
    cities = City.query.filter(City.name.like(f'{letter.upper()}%')).all()
    available = [city.name.lower() for city in cities if city.name.lower() not in session['used_cities']]
    return random.choice(available).capitalize() if available else None

# Запуск приложения
if __name__ == '__main__':
    init_db()  # Инициализация базы данных
    app.run(debug=True)