from app import app, db, Session, Member
from flask import Flask, render_template_string

# Basit bir test şablonu
TEST_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Seans Test</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; }
        .category { margin-bottom: 20px; padding: 10px; border: 1px solid #ccc; }
        h2 { color: #333; }
    </style>
</head>
<body>
    <h1>Seans Kategorileri</h1>
    
    {% for cat in categories %}
    <div class="category">
        <h2>{{ cat.name }} ({{ cat.items|length }} seans)</h2>
        <ul>
            {% for s in cat.items %}
            <li>ID: {{ s.id }}, Tarih: {{ s.date }}, Saat: {{ s.time }}, 
                Tamamlandı: {{ s.completed }}, Recurring: {{ s.is_recurring }}</li>
            {% else %}
            <li>Bu kategoride seans yok.</li>
            {% endfor %}
        </ul>
    </div>
    {% endfor %}
</body>
</html>
"""

with app.app_context():
    sessions = Session.query.order_by(Session.date.asc(), Session.time.asc()).all()
    
    # Kategorileri oluştur
    categories = [
        {
            'name': 'Planlandı',
            'icon': '📅',
            'bg': 'yellow-100',
            'color': 'yellow-800',
            'items': [s for s in sessions if not s.completed and not s.is_recurring]
        },
        {
            'name': 'Haftalık Seri',
            'icon': '🔄',
            'bg': 'blue-100',
            'color': 'blue-800',
            'items': [s for s in sessions if not s.completed and s.is_recurring]
        },
        {
            'name': 'Tamamlandı',
            'icon': '✓',
            'bg': 'green-100',
            'color': 'green-800',
            'items': [s for s in sessions if s.completed]
        }
    ]
    
    # Şablonu render et ve dosyaya kaydet
    rendered = render_template_string(TEST_TEMPLATE, categories=categories)
    with open("test_template_output.html", "w") as f:
        f.write(rendered)
        
    print("Test şablonu oluşturuldu: test_template_output.html")
