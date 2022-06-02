from settings import *

from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy(DATABASE_URL)


class Quiz(db.Model):
    id = db.Column(db.Integer ,primary_key=True)
    name = db.Column(db.String(100))
    rating = db.Column(db.Integer)


class Question(db.Model):
    id = db.Column(db.Integer,primary_key=True)
    quiz = db.Column(db.Integer,  db.ForeignKey("quiz.id"))
    question = db.Column(db.String(100))


class Answer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Integer, db.ForeignKey("question.id"))
    answer = db.Column(db.String(100))
    is_correct = db.Column(db.Boolean)


class UserData(db.Model):
    id = db.Column(db.UUID, primary_key=True)
    user = db.Column(db.String(100))
    under_test = db.Column(db.Boolean)
    passed_questions = db.Column(db.Integer)
    current_question = db.Column(db.Integer, db.ForeignKey("question.id"))
    quiz = db.Column(db.Integer, db.ForeignKey("question.id"))
    mark = db.Column(db.Integer)
    total_quiz = db.Column(db.Integer)