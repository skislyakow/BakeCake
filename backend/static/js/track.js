// Трекинг визитов: при загрузке страницы считывает UTM-метки из URL
// и отправляет POST /api/track/visit/ (PLAN.md, раздел «Атрибуция рекламы»).
(function () {
    if (window.__bcTrackDone) return;
    window.__bcTrackDone = true;

    var params = new URLSearchParams(window.location.search);
    var body = {
        utm_source: params.get('utm_source') || '',
        utm_medium: params.get('utm_medium') || '',
        utm_campaign: params.get('utm_campaign') || '',
        utm_content: params.get('utm_content') || '',
        utm_term: params.get('utm_term') || '',
        referrer: document.referrer || '',
        landing_path: window.location.pathname + window.location.search
    };

    var meta = document.querySelector('meta[name="csrf-token"]');
    fetch('/api/track/visit/', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-CSRFToken': meta ? meta.content : ''
        },
        body: JSON.stringify(body)
    }).catch(function () {
        // трекинг не критичен — молча прощаем ошибки сети
    });
})();