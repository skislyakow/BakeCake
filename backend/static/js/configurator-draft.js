// Черновик конфигуратора: чистая логика без DOM/сети (кандидат 7, .agents/PLAN.md).
// Компонент Vue в index.js остаётся тонкой привязкой к DOM, таймерам и api().
(function (global) {
    var REPEAT_KEY = 'bc_repeat';
    var PROFILE_KEY = 'bc_profile';

    var PHONE_RE = /^\+?\d[\d\s\-()]{6,}$/;
    var EMAIL_RE = /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,4}$/i;
    var NAME_RE = /^[a-zA-Zа-яА-ЯёЁ\s-]+$/;

    function trimStr(value) {
        return (value || '').toString().trim();
    }

    function storageGet(storage, key) {
        try {
            return storage ? storage.getItem(key) : null;
        } catch (e) {
            return null;
        }
    }

    function storageSet(storage, key, value) {
        try {
            if (storage) storage.setItem(key, value);
            return true;
        } catch (e) {
            return false;
        }
    }

    function storageRemove(storage, key) {
        try {
            if (storage) storage.removeItem(key);
        } catch (e) {}
    }

    function defaultSel(groups) {
        var sel = {};
        (groups || []).forEach(function (g) {
            sel[g.code] = null;
        });
        return sel;
    }

    function createState(groups) {
        return {
            Designed: false,
            Catalog: [],
            CatalogError: '',
            CatalogOpen: false,
            SelectedCake: null,
            Levels: null,
            Form: null,
            Topping: null,
            Berries: null,
            Decor: null,
            Words: '',
            Comments: '',
            Promo: '',
            Name: '',
            Phone: '',
            Email: '',
            Address: '',
            Dates: '',
            Time: '',
            DelivComments: '',
            Cost: 0,
            Quote: null,
            QuoteError: '',
            OrderError: '',
            OrderPlaced: null,
            Submitting: false,
            RushPercent: 20,
            ShowPayment: false,
            PdConsent: false,
            Groups: groups || [],
            Sel: defaultSel(groups),
        };
    }

    function resetState(state) {
        state.Designed = false;
        state.SelectedCake = null;
        state.Levels = state.Form = state.Topping = state.Berries = state.Decor = null;
        state.Words = state.Comments = state.Promo = '';
        state.Name = state.Phone = state.Email = state.Address = state.Dates = state.Time = state.DelivComments = '';
        state.Cost = 0;
        state.Quote = null;
        state.QuoteError = state.OrderError = '';
        state.OrderPlaced = null;
        state.Submitting = false;
        state.ShowPayment = false;
        state.PdConsent = false;
        state.Sel = defaultSel(state.Groups);
        return state;
    }

    function applyConfigDefaults(state, payload) {
        (payload.defaults || []).forEach(function (d) {
            state.Sel[d.code] = d.option_id;
            if (d.code === 'levels') state.Levels = d.option_id;
            if (d.code === 'form') state.Form = d.option_id;
            if (d.code === 'topping') state.Topping = d.option_id;
        });
        if (payload.rush_surcharge_percent != null) state.RushPercent = payload.rush_surcharge_percent;
        return state;
    }

    function isConfigured(state) {
        return !!(state.SelectedCake || (state.Levels && state.Topping));
    }

    function findGroup(state, code) {
        return (state.Groups || []).find(function (g) { return g.code === code; }) || null;
    }

    function labelFor(state, code) {
        var group = findGroup(state, code);
        if (!group) return '—';
        var option = group.options.find(function (o) { return o.id === state.Sel[code]; });
        return option ? option.title : '—';
    }

    function quoteBody(state) {
        var body = {
            promo_code: state.Promo,
            delivery_date: state.Dates,
            delivery_time: state.Time,
            delivery_mode: 'courier',
        };
        if (state.SelectedCake) {
            body.cake_id = state.SelectedCake.id;
        } else {
            body.levels = state.Levels;
            body.topping = state.Topping;
            if (state.Berries) body.berries = state.Berries;
            if (state.Decor) body.decor = state.Decor;
            body.words = state.Words;
            body.comment = state.Comments;
        }
        return body;
    }

    function orderBody(state) {
        var body = {
            promo_code: state.Promo,
            name: state.Name,
            phone: state.Phone,
            email: state.Email,
            address: state.Address,
            comment: state.Comments,
            courier_comment: state.DelivComments,
            delivery_date: state.Dates,
            delivery_time: state.Time,
            delivery_mode: 'courier',
            pd_consent: !!state.PdConsent,
        };
        if (state.SelectedCake) {
            body.cake_id = state.SelectedCake.id;
            body.detail = state.SelectedCake.description || '';
            if (state.SelectedCake.spec) body.spec = state.SelectedCake.spec;
        } else {
            body.spec = {
                levels: state.Levels,
                levels_title: labelFor(state, 'levels'),
                form: state.Form,
                form_title: labelFor(state, 'form'),
                topping: state.Topping,
                topping_title: labelFor(state, 'topping'),
                berries: state.Berries,
                berries_title: labelFor(state, 'berries'),
                decor: state.Decor,
                decor_title: labelFor(state, 'decor'),
                words: state.Words,
                comment: state.Comments,
            };
        }
        return body;
    }

    function readRepeat(sessionStorage) {
        var raw = storageGet(sessionStorage, REPEAT_KEY);
        if (!raw) return null;
        try {
            return JSON.parse(raw);
        } catch (e) {
            return null;
        }
    }

    function clearRepeat(sessionStorage) {
        storageRemove(sessionStorage, REPEAT_KEY);
    }

    function applyRepeat(state, item) {
        if (!item) return state;
        state.SelectedCake = null;
        state.Sel = defaultSel(state.Groups);
        state.CatalogOpen = true;
        if (item.cake_id) {
            var found = (state.Catalog || []).find(function (c) { return c.id === item.cake_id; }) || null;
            if (found) {
                state.SelectedCake = Object.assign({}, found, {spec: item.spec || null, detail: item.detail || ''});
            }
        } else if (item.spec) {
            var spec = item.spec;
            state.Levels = spec.levels || null;
            state.Topping = spec.topping || null;
            state.Berries = spec.berries || null;
            state.Decor = spec.decor || null;
            state.Sel.levels = spec.levels || null;
            state.Sel.form = spec.form || null;
            state.Sel.topping = spec.topping || null;
            state.Sel.berries = spec.berries || null;
            state.Sel.decor = spec.decor || null;
            state.Words = spec.words || '';
            state.Comments = spec.comment || '';
        }
        return state;
    }

    function readProfile(localStorage) {
        var raw = storageGet(localStorage, PROFILE_KEY);
        if (!raw) return null;
        try {
            return JSON.parse(raw);
        } catch (e) {
            return null;
        }
    }

    function writeProfile(localStorage, profile) {
        return storageSet(localStorage, PROFILE_KEY, JSON.stringify(profile || {}));
    }

    var validators = {
        required: function (message) {
            return function (value) {
                return value ? true : message;
            };
        },
        nameFormat: function (value) {
            if (!value) return '⚠ Укажите имя';
            if (!NAME_RE.test(value)) return '⚠ Недопустимые символы в имени';
            return true;
        },
        phoneFormat: function (value) {
            if (!value) return true;
            if (!PHONE_RE.test(value)) return '⚠ Формат телефона нарушен';
            return true;
        },
        emailFormat: function (value) {
            if (!value) return true;
            if (!EMAIL_RE.test(value)) return '⚠ Формат почты нарушен';
            return true;
        },
    };

    function schema1(validatorsMap) {
        var v = validatorsMap || validators;
        return {
            lvls: v.required(' количество уровней'),
            form: v.required(' форму торта'),
            topping: v.required(' топпинг'),
        };
    }

    function schema2(validatorsMap) {
        var v = validatorsMap || validators;
        return {
            name: v.required(' имя'),
            phone: v.required(' телефон'),
            email: v.required(' почту'),
            address: v.required(' адрес'),
            date: v.required(' дату доставки'),
            time: v.required(' время доставки'),
            name_format: v.nameFormat,
            phone_format: v.phoneFormat,
            email_format: v.emailFormat,
        };
    }

    var api = {
        REPEAT_KEY: REPEAT_KEY,
        PROFILE_KEY: PROFILE_KEY,
        createState: createState,
        resetState: resetState,
        applyConfigDefaults: applyConfigDefaults,
        isConfigured: isConfigured,
        labelFor: labelFor,
        quoteBody: quoteBody,
        orderBody: orderBody,
        readRepeat: readRepeat,
        clearRepeat: clearRepeat,
        applyRepeat: applyRepeat,
        readProfile: readProfile,
        writeProfile: writeProfile,
        validators: validators,
        schema1: schema1,
        schema2: schema2,
    };

    global.BC = global.BC || {};
    global.BC.draft = api;
})(typeof window !== 'undefined' ? window : globalThis);
