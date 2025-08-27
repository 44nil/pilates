from app import app, db, Session, app, Reservation, Member
from flask import render_template_string

debug_template = """
{% for cat in categories %}
<div style="margin-bottom: 20px; padding: 10px; border: 1px solid #ccc;">
  <h3>{{ cat.name }} ({{ cat.items|length }} seans)</h3>
  <ul>
  {% for s in cat.items %}
    <li>{{ s.date }} - {{ s.time }} (Kapasite: {{ s.capacity }}, Kalan: {{ s.spots_left }})</li>
  {% else %}
    <li>Hiç seans yok</li>
  {% endfor %}
  </ul>
</div>
{% endfor %}
"""

with app.app_context():
    sessions = Session.query.order_by(Session.date.asc(), Session.time.asc()).all()
    planned = [s for s in sessions if not s.completed]
    completed = [s for s in sessions if s.completed]
    recurring = [s for s in sessions if s.is_recurring]
    
    categories = [
        {'name': 'Planlandı', 'items': [s for s in planned if not s.is_recurring]},
        {'name': 'Haftalık Seri', 'items': [s for s in recurring if not s.completed]},
        {'name': 'Tamamlandı', 'items': completed}
    ]
    
    result = render_template_string(debug_template, categories=categories)
    
    with open('debug_output.html', 'w') as f:
        f.write(result)
    
    print("Hata ayıklama çıktısı debug_output.html dosyasına yazıldı.")
    
    # Sayı kontrolü
    print(f"Tüm seanslar: {len(sessions)}")
    print(f"Planlandı: {len(categories[0]['items'])}")
    print(f"Haftalık Seri: {len(categories[1]['items'])}")
    print(f"Tamamlandı: {len(categories[2]['items'])}")
