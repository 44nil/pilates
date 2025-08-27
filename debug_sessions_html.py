from flask import Flask, render_template_string
from app import app, db, Session, Member

app_test = Flask(__name__)
app_test.template_folder = '/Users/esranil/Desktop/pilatesweb-main/templates'

DEBUG_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Seans Hata Ayıklama</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; }
        .category { margin-bottom: 20px; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
        .sessions { margin-top: 10px; }
        .session { padding: 10px; border-bottom: 1px solid #eee; }
        h2 { margin-top: 0; }
        pre { background: #f5f5f5; padding: 10px; border-radius: 4px; overflow: auto; }
        .debug-info { margin-top: 40px; padding: 15px; background: #f0f0f0; border-radius: 5px; }
    </style>
</head>
<body>
    <h1>Seans Kategorileri Hata Ayıklama</h1>
    
    <div class="debug-info">
        <h3>Debug Bilgileri:</h3>
        <p>Toplam Seans Sayısı: {{ sessions|length }}</p>
        <p>Categories Değişkeni Tanımlı: {{ categories is defined }}</p>
        {% if categories is defined %}
        <p>Kategori Sayısı: {{ categories|length }}</p>
        {% endif %}
    </div>
    
    {% if categories is defined %}
        {% for cat in categories %}
        <div class="category">
            <h2>{{ cat.name }} ({{ cat.items|length if cat.items is defined and cat.items is iterable else 0 }} seans)</h2>
            {% if cat.items is defined and cat.items is iterable and cat.items|length > 0 %}
                <div class="sessions">
                    {% for s in cat.items %}
                        <div class="session">
                            ID: {{ s.id }} | 
                            Tarih: {{ s.date }} | 
                            Saat: {{ s.time }} |
                            Tamamlandı: {{ s.completed }} |
                            Recurring: {{ s.is_recurring }}
                        </div>
                    {% endfor %}
                </div>
            {% else %}
                <p>Bu kategoride seans bulunmuyor.</p>
            {% endif %}
        </div>
        {% endfor %}
    {% else %}
        <p>Categories değişkeni tanımlı değil!</p>
    {% endif %}
    
    <div class="debug-info">
        <h3>Tüm Seanslar:</h3>
        {% for s in sessions %}
            <div class="session">
                ID: {{ s.id }} | 
                Tarih: {{ s.date }} | 
                Saat: {{ s.time }} |
                Tamamlandı: {{ s.completed }} |
                Recurring: {{ s.is_recurring }}
            </div>
        {% endfor %}
    </div>
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
    
    # Render template and save as file
    with app_test.app_context():
        rendered = render_template_string(DEBUG_TEMPLATE, sessions=sessions, categories=categories)
        
    with open("debug_sessions.html", "w") as f:
        f.write(rendered)
        
    print("Debug HTML oluşturuldu: debug_sessions.html")
    print(f"Toplam seans sayısı: {len(sessions)}")
    
    for cat in categories:
        print(f"{cat['name']}: {len(cat['items'])} seans")
