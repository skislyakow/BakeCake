function csrfToken() {
    const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    if (match) return decodeURIComponent(match[1]);
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
        try {
            return await response.json();
        } catch (e) {
            return {ok: false, errors: {network: 'Не удалось связаться с сервером, попробуйте ещё раз'}};
        }
    } catch (e) {
        return {ok: false, errors: {network: 'Не удалось связаться с сервером, попробуйте ещё раз'}};
    }
}

function firstError(data) {
    if (!data) return 'Что-то пошло не так, попробуйте ещё раз';
    const errors = data.errors ? Object.values(data.errors) : [];
    return errors[0] || data.error || 'Что-то пошло не так, попробуйте ещё раз';
}

const BC = window.BC || {};
BC.api = api;
BC.csrfToken = csrfToken;
BC.firstError = firstError;
BC.logout = async function () {
    const data = await api('/api/auth/logout/', 'POST');
    if (data && data.ok) window.location.href = '/';
    return data;
};
BC.rules = {
    required: (message) => (value) => (value ? true : message),
    optional: (validator) => (value) => (!value ? true : validator(value)),
    phone: (message) => (value) => {
        if (!value) return true;
        return /^((8|\+7)[\- ]?)?(\(?\d{3}\)?[\- ]?)?[\d\- ]{7,10}$/.test(value) ? true : (message || '⚠ Формат телефона нарушен');
    },
    email: (message) => (value) => {
        if (!value) return true;
        return /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,4}$/i.test(value) ? true : (message || '⚠ Формат почты нарушен');
    },
    name: (message, options) => (value) => {
        if (!value) return true;
        const pattern = options && options.allowSpaces
            ? /^[a-zA-Zа-яА-ЯёЁ\s-]+$/
            : /^[a-zA-Zа-яА-Я]+$/;
        return pattern.test(value) ? true : (message || '⚠ Формат имени нарушен');
    },
    code: (message) => (value) => {
        if (!value) return true;
        return /^[a-zA-Z0-9]+$/.test(value) ? true : (message || '⚠ Формат кода нарушен');
    },
};
window.BC = BC;
