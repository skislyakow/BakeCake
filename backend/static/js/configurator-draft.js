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

    var PREVIEW_FORMS = {
        form_circle: 'circle',
        form_square: 'square',
        form_rectangle: 'rectangle',
    };

    var PREVIEW_TOPPINGS = {
        topping_none: { color: '#F6E7D6', drip: false },
        topping_white: { color: '#FFF6EC', drip: true },
        topping_caramel: { color: '#D9A05B', drip: true },
        topping_maple: { color: '#C98B47', drip: true },
        topping_strawberry: { color: '#E98A9A', drip: true },
        topping_blueberry: { color: '#8B7BC0', drip: true },
        topping_chocolate: { color: '#7A4A32', drip: true },
    };

    var PREVIEW_BERRIES = {
        berry_blackberry: { color: '#3E2A4D', accent: '#5B3A6E' },
        berry_raspberry: { color: '#D6455D', accent: '#E4687D' },
        berry_blueberry: { color: '#5B6BB5', accent: '#7C8BD0' },
        berry_strawberry: { color: '#E23B4E', accent: '#F06A78' },
    };

    var PREVIEW_DECOR = {
        decor_pistachio: { color: '#9CB86B', rx: 5, ry: 3, rotate: -20 },
        decor_meringue: { color: '#F3D9C4', rx: 7, ry: 8, rotate: 0 },
        decor_hazelnut: { color: '#A9743F', rx: 6, ry: 5, rotate: 15 },
        decor_pecan: { color: '#8E5A32', rx: 8, ry: 4, rotate: -10 },
        decor_marshmallow: { color: '#F7E7EA', rx: 7, ry: 6, rotate: 0 },
        decor_marzipan: { color: '#F0C987', rx: 6, ry: 5, rotate: 25 },
    };

    var PREVIEW_FALLBACKS = {
        levels: [['1', 'level_1'], ['2', 'level_2'], ['3', 'level_3']],
        form: [['круг', 'form_circle'], ['квадрат', 'form_square'], ['прямоуголь', 'form_rectangle']],
        topping: [
            ['без', 'topping_none'],
            ['бел', 'topping_white'],
            ['карамел', 'topping_caramel'],
            ['клен', 'topping_maple'],
            ['клубнич', 'topping_strawberry'],
            ['чернич', 'topping_blueberry'],
            ['шоколад', 'topping_chocolate'],
        ],
        berries: [
            ['ежевик', 'berry_blackberry'],
            ['малин', 'berry_raspberry'],
            ['голубик', 'berry_blueberry'],
            ['клубник', 'berry_strawberry'],
        ],
        decor: [
            ['фисташ', 'decor_pistachio'],
            ['безе', 'decor_meringue'],
            ['фундук', 'decor_hazelnut'],
            ['пекан', 'decor_pecan'],
            ['маршмел', 'decor_marshmallow'],
            ['марципан', 'decor_marzipan'],
        ],
    };

    function selectedOption(state, code) {
        var group = findGroup(state, code);
        if (!group) return null;
        return (group.options || []).find(function (o) { return o.id === state.Sel[code]; }) || null;
    }

    function previewKey(state, code) {
        // preview_key из БД главный; названия — запасной путь для старых данных.
        var option = selectedOption(state, code);
        if (!option) return '';
        var key = trimStr(option.preview_key);
        if (key) return key;
        var title = trimStr(option.title).toLowerCase();
        var pairs = PREVIEW_FALLBACKS[code] || [];
        for (var i = 0; i < pairs.length; i += 1) {
            if (title.indexOf(pairs[i][0]) !== -1) return pairs[i][1];
        }
        return '';
    }

    function buildTiers(levels, form) {
        // Снизу вверх: каждый следующий ярус уже и ниже, с небольшим зазором.
        var widthScale = form === 'rectangle' ? 1.22 : 1;
        var tiers = [];
        var bottom = 244;
        for (var i = 0; i < levels; i += 1) {
            var width = Math.round((190 - i * 40) * widthScale);
            var height = 64 - i * 6;
            var y = bottom - height;
            tiers.push({
                x: Math.round(160 - width / 2),
                y: y,
                width: width,
                height: height,
                radius: form === 'circle' ? Math.min(26, Math.round(width * 0.14)) : 7,
                topRy: form === 'circle' ? Math.max(8, Math.round(width * 0.09)) : 8,
            });
            bottom = y - 5;
        }
        return tiers;
    }

    function previewModel(state) {
        if (state.SelectedCake) {
            return {
                cake: true,
                cakeImage: state.SelectedCake.image_url || '',
                cakeName: state.SelectedCake.name || '',
                label: state.SelectedCake.name || 'Готовый торт',
                levels: 0,
                form: '',
                bodyColor: '',
                toppingColor: '',
                tiers: [],
                drips: [],
                berries: [],
                decor: [],
                inscription: '',
                inscriptionY: 0,
                inscriptionSize: 13,
            };
        }

        var levelKey = previewKey(state, 'levels');
        var levelMatch = /^level_([123])$/.exec(levelKey);
        var levels = levelMatch ? Number(levelMatch[1]) : 1;
        var form = PREVIEW_FORMS[previewKey(state, 'form')] || 'circle';
        var topping = PREVIEW_TOPPINGS[previewKey(state, 'topping')] || PREVIEW_TOPPINGS.topping_none;
        var berry = PREVIEW_BERRIES[previewKey(state, 'berries')] || null;
        var decor = PREVIEW_DECOR[previewKey(state, 'decor')] || null;

        var tiers = buildTiers(levels, form);
        var top = tiers[tiers.length - 1];
        var topCenterY = top.y + top.topRy;

        var drips = [];
        if (topping.drip) {
            tiers.forEach(function (tier) {
                var count = 4;
                for (var i = 0; i < count; i += 1) {
                    var r = 4 + ((i + levels) % 3) * 1.5;
                    drips.push({
                        cx: Math.round(tier.x + tier.width * ((i + 0.5) / count)),
                        cy: Math.round(tier.y + r + 1),
                        r: r,
                        fill: topping.color,
                    });
                }
            });
        }

        var berries = [];
        if (berry) {
            [[-30, 2], [-15, -2], [0, 3], [15, -2], [30, 2], [0, -9]].forEach(function (offset, index) {
                berries.push({
                    cx: Math.round(160 + offset[0]),
                    cy: Math.round(topCenterY + offset[1]),
                    r: index === 5 ? 5 : 7,
                    fill: index % 2 ? berry.accent : berry.color,
                    leaf: index % 2 === 0,
                });
            });
        }

        var decorItems = [];
        if (decor) {
            [[-44, 10], [44, 10], [-24, 17], [24, 17], [0, 22]].forEach(function (offset) {
                decorItems.push({
                    cx: Math.round(160 + offset[0]),
                    cy: Math.round(topCenterY + offset[1]),
                    rx: decor.rx,
                    ry: decor.ry,
                    fill: decor.color,
                    rotate: decor.rotate,
                });
            });
        }

        var inscription = trimStr(state.Words);
        if (inscription.length > 18) inscription = inscription.slice(0, 17).trim() + '…';

        // Надпись подгоняем под ширину верхнего яруса, иначе на трёх уровнях она вылезает.
        var inscriptionSize = 13;
        if (inscription) {
            var fit = Math.floor((top.width - 8) / Math.max(1, inscription.length * 0.58));
            inscriptionSize = Math.max(9, Math.min(13, fit));
        }

        var labelParts = [];
        ['levels', 'form', 'topping', 'berries', 'decor'].forEach(function (code) {
            var title = labelFor(state, code);
            if (title && title !== 'не выбрано') labelParts.push(title);
        });
        if (inscription) labelParts.push('надпись «' + inscription + '»');

        return {
            cake: false,
            cakeImage: '',
            cakeName: '',
            label: labelParts.join(', '),
            levels: levels,
            form: form,
            bodyColor: '#F7E9DA',
            toppingColor: topping.color,
            tiers: tiers,
            drips: drips,
            berries: berries,
            decor: decorItems,
            inscription: inscription,
            inscriptionY: Math.round(top.y + top.height * 0.62 + 5),
            inscriptionSize: inscriptionSize,
        };
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
        previewModel: previewModel,
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
