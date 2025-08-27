from app import app, db, Session

with app.app_context():
    print('Mevcut Seans Sayısı:', Session.query.count())
