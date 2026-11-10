// Черновик конфигуратора: чистая логика без DOM/сети (кандидат 7, .agents/PLAN.md).
// Компонент Vue в index.js остаётся тонкой привязкой к DOM, таймерам и api().
(function (global) {
    var REPEAT_KEY = 'bc_repeat';

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
            Config: null,
            ConfigError: '',
            Designed: false,
            Catalog: [],
            CatalogError: '',
            CatalogOpen: false,
            SelectedCake: null,
            Authed: false,
            Hydrated: false,
            SaveTimer: null,
            QuoteTimer: null,
            QuoteTicket: 0,
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
            Quote: null,
            QuoteError: '',
            OrderError: '',
            OrderPlaced: null,
            Submitting: false,
            RushPercent: 20,
            ShowPayment: false,
            PdConsent: false,
            DatesMin: '',
            TimeFrom: '',
            TimeTo: '',
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
        state.Quote = null;
        state.QuoteError = state.OrderError = '';
        state.OrderPlaced = null;
        state.Submitting = false;
        state.ShowPayment = false;
        state.PdConsent = false;
        state.Sel = defaultSel(state.Groups);
        return state;
    }

    function todayIso() {
        var now = new Date();
        var month = String(now.getMonth() + 1).padStart(2, '0');
        var day = String(now.getDate()).padStart(2, '0');
        return now.getFullYear() + '-' + month + '-' + day;
    }

    // Поля и префиксы id повторяют вёрстку: levels → lvls / num, остальные = code.
    function mapGroup(group) {
        return Object.assign({}, group, {
            required: !!group.is_required,
            field: group.code === 'levels' ? 'lvls' : group.code,
            prefix: group.code === 'levels' ? 'num' : group.code,
        });
    }

    function applyConfig(state, payload) {
        var delivery = payload.delivery || {};
        state.Config = payload;
        state.Groups = (payload.groups || []).map(mapGroup);
        state.Sel = defaultSel(state.Groups);
        state.DatesMin = todayIso();
        state.TimeFrom = delivery.from || '';
        state.TimeTo = delivery.to || '';
        if (delivery.rush_surcharge_percent != null) {
            state.RushPercent = delivery.rush_surcharge_percent;
        }
        return state;
    }

    function isConfigured(state) {
        if (state.SelectedCake) return true;
        if (!state.Config) return false;
        return (state.Config.groups || []).every(function (g) {
            return !g.is_required || !!state.Sel[g.code];
        });
    }

    function findGroup(state, code) {
        return (state.Groups || []).find(function (g) { return g.code === code; }) || null;
    }

    function labelFor(state, code) {
        var group = findGroup(state, code);
        if (!group) return 'не выбрано';
        var option = (group.options || []).find(function (o) { return o.id === state.Sel[code]; });
        return option ? option.title : 'не выбрано';
    }

    function specBody(state) {
        var spec = {};
        (state.Groups || []).forEach(function (g) {
            if (state.Sel[g.code]) spec[g.code] = state.Sel[g.code];
        });
        var inscription = trimStr(state.Words);
        if (inscription) spec.inscription = inscription;
        return spec;
    }

    function quoteBody(state) {
        // null, пока серверу нечего считать: нужны дата и время, а для своего
        // торта — ещё и все обязательные группы.
        if (!state.Dates || !state.Time) return null;
        if (state.SelectedCake) {
            return {
                cake_id: state.SelectedCake.id,
                delivery_date: state.Dates,
                delivery_time: state.Time,
                promo_code: state.Promo,
            };
        }
        if (!isConfigured(state)) return null;
        return {
            spec: specBody(state),
            delivery_date: state.Dates,
            delivery_time: state.Time,
            promo_code: state.Promo,
        };
    }

    function orderBody(state) {
        var body = {
            name: trimStr(state.Name),
            phone: trimStr(state.Phone),
            email: trimStr(state.Email),
            address: trimStr(state.Address),
            delivery_date: state.Dates,
            delivery_time: state.Time,
            comment: trimStr(state.Comments),
            courier_comment: trimStr(state.DelivComments),
            promo_code: trimStr(state.Promo),
            pd_consent: !!state.PdConsent,
        };
        if (state.SelectedCake) {
            body.cake_id = state.SelectedCake.id;
        } else {
            body.spec = specBody(state);
        }
        return body;
    }

    function previewCost(state) {
        if (state.Quote) return state.Quote.total;
        if (state.SelectedCake) return state.SelectedCake.price;
        if (!state.Config) return 0;
        var sum = 0;
        (state.Config.groups || []).forEach(function (g) {
            var option = (g.options || []).find(function (o) { return o.id === state.Sel[g.code]; });
            if (option) sum += option.price_delta;
        });
        if (trimStr(state.Words)) sum += state.Config.inscription_price || 0;
        return sum;
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
        state.Quote = null;
        state.QuoteError = '';
        var cakeId = typeof item.cake === 'number' ? item.cake : item.cake_id;
        if (typeof cakeId === 'number') {
            // Готовый торт: Order.spec хранит {"cake": id}.
            var cake = (state.Catalog || []).find(function (c) { return c.id === cakeId; }) || null;
            if (cake) {
                state.SelectedCake = cake;
                state.Designed = true;
            }
            return state;
        }
        // Свой торт: в spec лежат коды групп и надпись. Опция могла исчезнуть —
        // тогда группу не трогаем.
        (state.Groups || []).forEach(function (g) {
            var option = (g.options || []).find(function (o) { return o.id === item[g.code]; });
            if (option) state.Sel[g.code] = option.id;
        });
        if (typeof item.inscription === 'string') state.Words = item.inscription;
        return state;
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
        createState: createState,
        resetState: resetState,
        applyConfig: applyConfig,
        isConfigured: isConfigured,
        labelFor: labelFor,
        previewCost: previewCost,
        quoteBody: quoteBody,
        orderBody: orderBody,
        readRepeat: readRepeat,
        clearRepeat: clearRepeat,
        applyRepeat: applyRepeat,
        validators: validators,
        schema1: schema1,
        schema2: schema2,
    };

    global.BC = global.BC || {};
    global.BC.draft = api;
})(typeof window !== 'undefined' ? window : globalThis);
