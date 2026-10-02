// Общий помощник для обращений к API. Формат ответа — {ok, errors|error, ...} (PLAN.md, раздел 4.1).
function csrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : '';
}

async function api(url, method = 'GET', body = null) {
    const options = {
        method,
        credentials: 'same-origin',
        headers: {'Accept': 'application/json', 'X-CSRFToken': csrfToken()},
    };
    if (body !== null) {
        options.headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(body);
    }
    try {
        const response = await fetch(url, options);
        return await response.json();
    } catch (e) {
        return {ok: false, errors: {network: 'Не удалось связаться с сервером, попробуйте ещё раз'}};
    }
}

// Первое сообщение об ошибке из ответа API — для показа пользователю.
function firstError(data) {
    const errors = data.errors ? Object.values(data.errors) : [];
    return errors[0] || data.error || 'Что-то пошло не так, попробуйте ещё раз';
}
