from . import db


class Collins(db.Model):
    __tablename__ = 'vocabulary'
    rowid = db.Column(db.Integer, primary_key=True)
    voc = db.Column(db.String(64))
    star = db.Column(db.Integer)
    remember = db.Column(db.Integer)
    Definition = db.Column(db.String(64))
    phonetic = db.Column(db.String(64))


class Coca(db.Model):
    __tablename__ = 'americanyoudao'
    rowid = db.Column(db.Integer, primary_key=True)
    voc = db.Column(db.String(64))
    rank = db.Column(db.Integer)
    pos = db.Column(db.String(64))
    remember = db.Column(db.Integer)
    YD_voc = db.Column(db.String(64))
    Definition = db.Column(db.String(64))
    phonetic = db.Column(db.String(64))


class Book(db.Model):
    __tablename__ = 'Book'
    rowid = db.Column(db.Integer, primary_key=True)
    voc = db.Column(db.String(64))
    rank = db.Column(db.Integer)
    pos = db.Column(db.String(64))
    remember = db.Column(db.Integer)
    YD_voc = db.Column(db.String(64))
    Definition = db.Column(db.String(64))
    phonetic = db.Column(db.String(64))
