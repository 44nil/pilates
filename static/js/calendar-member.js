// Takvim boş slot tıklama işlevi
document.addEventListener('DOMContentLoaded', function() {
  // Boş slotlara tıklama olayı dinleyicisini ekle
  document.querySelectorAll('.empty-slot-member').forEach(function(btn) {
    btn.addEventListener('click', function() {
      const day = this.getAttribute('data-day');
      const time = this.getAttribute('data-time');
      
      if (confirm(`${day} tarihinde ${time} saatinde yeni bir seansa katılmak istiyor musunuz?`)) {
        // Form oluştur ve submit et
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '/create_empty_session_and_join';
        
        // Gizli alanları ekle
        const dayInput = document.createElement('input');
        dayInput.type = 'hidden';
        dayInput.name = 'day';
        dayInput.value = day;
        
        const timeInput = document.createElement('input');
        timeInput.type = 'hidden';
        timeInput.name = 'time';
        timeInput.value = time;
        
        // Form elemanlarını forma ekle
        form.appendChild(dayInput);
        form.appendChild(timeInput);
        
        // Formu body'ye ekle ve submit et
        document.body.appendChild(form);
        form.submit();
      }
    });
  });
});
