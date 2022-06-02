from settings import *
from models import db, Quiz, Answer, Question, UserData

from flask import Flask, request
from telebot import types
import telebot

import os
import logging
import json
import random

bot = telebot.TeleBot(token=BOT_TOKEN)
server = Flask(__name__)

logger = telebot.logger
logger.setLevel(logging.WARNING if os.env['environment'] == 'prod' else logging.DEBUG)


@bot.message_handler(commands=['menu'])
def show_current_menu(message):
    menu_markup = types.ReplyKeyboardMarkup()
    start_button = types.KeyboardButton("Розпочати тест")
    help_button = types.KeyboardButton("Допомога")
    menu_markup.row(start_button)
    menu_markup.row(help_button)
    bot.send_message(message.chat.id, text="Оберіть опцію:", reply_markup=menu_markup)


@bot.message_handler(commands="help")
def get_help(message):
    bot.send_message(message.chat.id, text="Телеграм-бот для опитувань.\n Для початку роботи введіть: /start\n Для зупинки бота натисніть: /stop")


@bot.message_handler(commands=['stop'])
def stop_quiz(message):
    menu_markup = types.ReplyKeyboardMarkup()
    start_button = types.KeyboardButton("Розпочати опитування")
    help_button = types.KeyboardButton("Допомога")
    menu_markup.row(start_button)
    menu_markup.row(help_button)

    session = UserData.query.filter_by(user=message.from_user.id).first()
    if session:
        db.session.under_test = False
        db.session.commit()
        bot.send_message(message.chat.id, text="Опитування було відмінено", reply_markup=menu_markup)
        return

    bot.send_message(message.chat.id, text="Опитування не було розпочате", reply_markup=menu_markup)


@bot.message_handler(commands=['start'])
def start_quiz_menu(message):
    session = UserData.query.filter_by(user=message.from_user.id).first()

    if session:
        bot.send_message(message.chat.id, text="Помилка. Тест вже розпочато")
        return

    inline_markup = types.InlineKeyboardMarkup()
    quizzes = Quiz.query.order_by('rating').all()

    for quiz in quizzes:
        quiz_btn = types.InlineKeyboardButton(quiz.name)
        quiz_btn.callback_data = '{"quiz_id": ' + str(quiz.id)+"}"
        inline_markup.add(quiz_btn)

    bot.send_message(message.chat.id, text="Оберіть опитування:", reply_markup=inline_markup)


@bot.message_handler(content_types="text")
def text_commands(message):

    if "Розпочати опитування" in message.text:
        start_quiz_menu(message)
        return

    if "Допомога" in message.text:
        get_help(message)
        return

    if "Зупинити опитування" in message.text:
        stop_quiz(message)
        return


def is_answer_callback(callback):
    return 'answer_id' in callback.data


def create_answers_buttons(question_id):
    answers = Answer.query.filter_by(question=question_id).all()

    inline_markup = types.InlineKeyboardMarkup()
    for answer in answers:
        inline_btn = types.InlineKeyboardButton(answer.answer)
        inline_btn.callback_data = f'{"answer_id":{answer.id}}';
        inline_markup.add(inline_btn)

    return inline_markup


def send_question(chat_id, question, num):
    inline_markup = create_answers_buttons(question.id)
    num += 1
    bot.send_message(chat_id, text=f"№{num}: {question.question}", reply_markup=inline_markup)


def quiz_finished(session, chat_id):
    menu_markup = types.ReplyKeyboardMarkup()
    start_button = types.KeyboardButton("Розпочати опитування")
    help_button = types.KeyboardButton("Допомога")
    menu_markup.row(start_button)
    menu_markup.row(help_button)

    recommendation = 'Все чудово, так тримати!' if session.mark == session.passed_questions else 'Було б добре покращити знання в області ІТ'
    bot.send_message(chat_id, text="Вітаю! Ви завершили опитування", reply_markup=menu_markup)
    bot.send_message(chat_id, text=f"Результат: {'✅' * session.mark}{'❌' * (session.passed_questions - session.mark)}")
    bot.send_message(chat_id, text=recommendation)

    db.session.under_test = False
    db.session.total_quiz += 1
    db.session.commit()


@bot.callback_query_handler(func=is_answer_callback)
def user_answered(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)

    data = json.loads(call.data)
    answer_id = data['answer_id']

    answer = Answer.query.filter_by(id=answer_id).first()

    if not answer:
        bot.send_message(call.message.chat.id, text="Відповідь некорректна")

    session = UserData.query.filter_by(user=call.from_user.id, under_test=False).first()

    if not session:
        bot.send_message(call.message.chat.id, text="Опитування ще не розпочато")
        return

    question = Question.query.filter_by(quiz=session.quiz, id=answer.question).first()

    if not question:
        bot.send_message(call.message.chat.id, text="Щось пішло не так")
        return

    if answer.correct:
        session.mark += 1

    session.passed_questions += 1

    if session.passed_questions >= TESTS_AMOUNT:
        quiz_finished(session, call.from_user.id)
        return

    questions = Question.query.filter_by(quiz=session.quiz).all()
    question = random.choice(questions)
    session.current_question = question.id
    db.session.commit()

    send_question(call.message.chat.id, question, session.passed_questions)


def quiz_handler(callback):
    return 'quiz_id' in callback.data


@bot.callback_query_handler(func=quiz_handler)
def create_session(call):
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id)

    session = UserData.query.filter_by(user=call.from_user.id).first()
    if session and session.under_test is True:
        bot.send_message(call.message.chat.id, text="Опитування вже розпочато")
        return

    data = json.loads(call.data)
    quiz_id = int(data['quiz_id'])
    quiz = Quiz.query.filter_by(id=quiz_id).first()
    quiz.rating += 1

    bot.send_message(call.message.chat.id, text="Тема: "+quiz.name)

    questions = Question.query.filter_by(quiz=quiz_id).all()
    if len(questions):
        question = random.choice(questions)
        if not session:
            session = UserData(user=call.from_user.id, passed_questions=0, current_question=question.id, mark=0, quiz=quiz_id)

            db.session.add(session)
            db.session.commit()

        menu_markup = types.ReplyKeyboardMarkup()
        start_button = types.KeyboardButton("Зупинити опитування")
        help_button = types.KeyboardButton("Допомога")
        menu_markup.row(start_button)
        menu_markup.row(help_button)

        bot.send_message(call.message.chat.id, "Опитування розпочато:", reply_markup=menu_markup)
        send_question(call.message.chat.id, question, session.passed_questions)
        db.flush()


@server.route(f"/{BOT_ENDPOINT}/", methods=['POST'])
def process_message():
    json = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json)
    bot.process_new_updates([update])
    return "ok", 200


server.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5050)))
