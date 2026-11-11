// Юнит-проверки чистой фронтовой логики без браузера.
// Запуск: node scripts/test_frontend.js
const path = require('path');

global.window = global;
global.document = {
    cookie: '',
    querySelector: function () { return null; },
};

require(path.join(__dirname, '..', 'backend', 'static', 'js', 'api.js'));
require(path.join(__dirname, '..', 'backend', 'static', 'js', 'configurator-draft.js'));

const draft = global.BC.draft;
let failed = 0;

function assert(condition, message) {
    if (!condition) {
        failed += 1;
        console.error('FAIL: ' + message);
    } else {
        console.log('OK   ' + message);
    }
}

function testCsrfToken() {
    let meta = null;
    document.querySelector = function () { return meta; };

    document.cookie = 'sessionid=abc; csrftoken=cookie-token';
    assert(global.BC.csrfToken() === 'cookie-token', 'csrfToken берёт cookie первым');

    document.cookie = 'csrftoken=' + encodeURIComponent('token with space');
    assert(global.BC.csrfToken() === 'token with space', 'csrfToken декодирует cookie');

    document.cookie = 'sessionid=abc';
    meta = { content: 'meta-token' };
    assert(global.BC.csrfToken() === 'meta-token', 'csrfToken падает на meta без cookie');

    meta = null;
    assert(global.BC.csrfToken() === '', 'csrfToken без cookie и meta — пустая строка');
}

function testDraft() {
    const groups = [
        { code: 'levels', title: 'Уровни', is_required: true, options: [{ id: 1, title: '1', price_delta: 400 }, { id: 2, title: '2', price_delta: 700 }] },
        { code: 'form', title: 'Форма', is_required: true, options: [{ id: 3, title: 'Круг', price_delta: 100 }] },
        { code: 'topping', title: 'Топпинг', is_required: true, options: [{ id: 4, title: 'Крем', price_delta: 0 }] },
        { code: 'berries', title: 'Ягоды', is_required: false, options: [{ id: 5, title: 'Малина', price_delta: 200 }] },
    ];
    const config = {
        groups: groups,
        inscription_price: 500,
        delivery: { from: '10:00', to: '23:00', lead_time_hours: 24, rush_surcharge_percent: 20 },
    };

    const state = draft.createState([]);
    draft.applyConfig(state, config);
    assert(state.Groups.length === 4, 'config groups mapped');
    assert(state.Groups[0].required === true && state.Groups[0].field === 'lvls' && state.Groups[0].prefix === 'num', 'levels mapped to lvls/num');
    assert(state.Groups[1].field === 'form' && state.Groups[1].prefix === 'form', 'form keeps code');
    assert(state.TimeFrom === '10:00' && state.TimeTo === '23:00', 'delivery window set');
    assert(/^\d{4}-\d{2}-\d{2}$/.test(state.DatesMin), 'date min set');
    assert(draft.quoteBody(state) === null, 'quote null without date/time');

    state.Sel.levels = 1;
    state.Sel.form = 3;
    state.Sel.topping = 4;
    assert(draft.isConfigured(state) === true, 'configured with required groups');
    assert(draft.quoteBody(state) === null, 'quote null without date');
    state.Dates = '2026-11-20';
    state.Time = '15:00';
    state.Words = '  С юбилеем  ';
    state.Sel.berries = 5;
    state.Promo = 'SALE';
    assert(draft.isConfigured(state) === true, 'still configured');
    const quote = draft.quoteBody(state);
    assert(quote && quote.spec.levels === 1 && quote.spec.form === 3 && quote.spec.topping === 4 && quote.spec.berries === 5, 'quote spec uses group codes');
    assert(quote.spec.inscription === 'С юбилеем', 'quote inscription trimmed');
    assert(quote.delivery_date === '2026-11-20' && quote.delivery_time === '15:00' && quote.promo_code === 'SALE', 'quote delivery/promo');

    assert(draft.labelFor(state, 'levels') === '1', 'labelFor returns option title');
    assert(draft.labelFor(state, 'decor') === 'не выбрано', 'labelFor unknown group');

    state.Name = '  Анна ';
    state.Phone = '+79001234567';
    state.Email = 'a@b.ru';
    state.Address = 'Москва';
    state.Comments = 'Комментарий';
    state.DelivComments = 'Домофон';
    state.PdConsent = true;
    const order = draft.orderBody(state);
    assert(order.name === 'Анна' && order.phone === '+79001234567' && order.address === 'Москва', 'order customer fields trimmed');
    assert(order.pd_consent === true, 'order sends pd_consent');
    assert(order.spec && order.spec.levels === 1 && order.spec.inscription === 'С юбилеем', 'order spec clean');
    assert(!('levels_title' in order.spec) && !('words' in order.spec) && !('comment' in order.spec), 'order spec has no legacy keys');
    assert(!('detail' in order) && !('delivery_mode' in order), 'order body has no unknown keys');

    assert(draft.previewCost(state) === 400 + 100 + 0 + 200 + 500, 'preview sums options + inscription');
    state.Quote = { total: 1300 };
    assert(draft.previewCost(state) === 1300, 'quote total wins');

    const cakeState = draft.createState([]);
    draft.applyConfig(cakeState, config);
    cakeState.Catalog = [{ id: 77, name: 'Торт', price: 900 }];
    draft.applyRepeat(cakeState, { cake: 77 });
    assert(cakeState.SelectedCake && cakeState.SelectedCake.id === 77, 'repeat cake restored');
    assert(cakeState.Designed === true, 'repeat cake opens checkout');
    assert(draft.previewCost(cakeState) === 900, 'cake price as preview');
    const cakeQuote = draft.quoteBody(cakeState);
    cakeState.Dates = '2026-11-20';
    cakeState.Time = '15:00';
    const cakeQuoteWithSlot = draft.quoteBody(cakeState);
    assert(cakeQuote === null && cakeQuoteWithSlot.cake_id === 77 && !('spec' in cakeQuoteWithSlot), 'cake quote sends cake_id only');

    const custom = draft.createState([]);
    draft.applyConfig(custom, config);
    draft.applyRepeat(custom, { levels: 2, form: 3, topping: 4, berries: 5, inscription: 'С днём' });
    assert(custom.Sel.levels === 2 && custom.Sel.berries === 5 && custom.Words === 'С днём', 'repeat custom spec restored');
    assert(custom.SelectedCake === null, 'repeat custom has no cake');
}

function testPreview() {
    const groups = [
        { code: 'levels', title: 'Уровни', is_required: true, options: [
            { id: 11, title: '1 уровень', price_delta: 400, preview_key: 'level_1' },
            { id: 12, title: '2 уровня', price_delta: 750, preview_key: 'level_2' },
            { id: 13, title: '3 уровня', price_delta: 1100, preview_key: 'level_3' },
        ] },
        { code: 'form', title: 'Форма', is_required: true, options: [
            { id: 21, title: 'Круг', price_delta: 400, preview_key: 'form_circle' },
            { id: 22, title: 'Квадрат', price_delta: 600, preview_key: 'form_square' },
            { id: 23, title: 'Прямоугольник', price_delta: 1000, preview_key: 'form_rectangle' },
        ] },
        { code: 'topping', title: 'Топпинг', is_required: true, options: [
            { id: 31, title: 'Без топпинга', price_delta: 0, preview_key: 'topping_none' },
            { id: 32, title: 'Карамельный сироп', price_delta: 180, preview_key: 'topping_caramel' },
        ] },
        { code: 'berries', title: 'Ягоды', is_required: false, options: [
            { id: 41, title: 'Малина', price_delta: 300, preview_key: 'berry_raspberry' },
        ] },
        { code: 'decor', title: 'Декор', is_required: false, options: [
            { id: 51, title: 'Фисташки', price_delta: 300, preview_key: 'decor_pistachio' },
        ] },
    ];
    const state = draft.createState([]);
    draft.applyConfig(state, { groups: groups, inscription_price: 500 });

    let preview = draft.previewModel(state);
    assert(preview.levels === 1 && preview.tiers.length === 1, 'preview defaults to one tier');
    assert(preview.form === 'circle' && preview.toppingColor === '#F6E7D6', 'preview defaults to circle without topping');
    assert(preview.berries.length === 0 && preview.decor.length === 0, 'preview has no extras by default');
    assert(preview.inscription === '' && preview.inscriptionY > 0, 'preview without inscription');
    assert(!preview.label.includes('не выбрано'), 'preview label skips empty choices');

    state.Sel.levels = 12;
    state.Sel.form = 22;
    state.Sel.topping = 32;
    state.Sel.berries = 41;
    state.Sel.decor = 51;
    state.Words = 'С днём рождения и счастья';
    preview = draft.previewModel(state);
    assert(preview.levels === 2 && preview.tiers.length === 2, 'preview stacks two tiers');
    assert(preview.form === 'square', 'preview follows form');
    assert(preview.toppingColor === '#D9A05B' && preview.drips.length > 0, 'preview draws topping and drips');
    assert(preview.berries.length === 6 && preview.decor.length === 5, 'preview adds berries and decor');
    assert(preview.inscription.endsWith('…') && preview.inscription.length <= 18, 'preview trims long inscription');
    assert(preview.label.includes('2 уровня') && preview.label.includes('Малина'), 'preview label describes choices');

    state.Sel.levels = 13;
    state.Sel.form = 21;
    const tall = draft.previewModel(state);
    assert(tall.tiers.length === 3, 'preview stacks three tiers');
    assert(tall.inscriptionSize === 9, 'preview shrinks inscription on a narrow top tier');

    state.Sel.levels = 11;
    state.Sel.form = 23;
    const rectangle = draft.previewModel(state);
    assert(rectangle.tiers[0].width > preview.tiers[0].width, 'rectangle is wider than square');

    // Fallback: старые опции без preview_key узнаются по названию.
    const legacy = draft.createState([]);
    draft.applyConfig(legacy, { groups: [
        { code: 'levels', title: 'Уровни', is_required: true, options: [{ id: 1, title: '3 уровня', price_delta: 1100 }] },
        { code: 'form', title: 'Форма', is_required: true, options: [{ id: 2, title: 'Круг', price_delta: 400 }] },
        { code: 'topping', title: 'Топпинг', is_required: true, options: [{ id: 3, title: 'Шоколад', price_delta: 200 }] },
    ] });
    legacy.Sel = { levels: 1, form: 2, topping: 3 };
    const legacyPreview = draft.previewModel(legacy);
    assert(legacyPreview.levels === 3 && legacyPreview.toppingColor === '#7A4A32', 'preview falls back to option titles');

    const cake = draft.createState([]);
    cake.SelectedCake = { id: 7, name: 'Медовик', image_url: '/static/img/image1.png' };
    const cakePreview = draft.previewModel(cake);
    assert(cakePreview.cake === true && cakePreview.cakeImage === '/static/img/image1.png', 'preview switches to selected cake');
}

function testStorage() {
    const store = {
        value: null,
        getItem: function () { return this.value; },
        removeItem: function () { this.value = null; },
    };
    assert(draft.readRepeat(store) === null, 'readRepeat без значения');
    store.value = '{"cake": 5}';
    assert(draft.readRepeat(store).cake === 5, 'readRepeat парсит JSON');
    store.value = '{broken';
    assert(draft.readRepeat(store) === null, 'readRepeat глотает битый JSON');
    store.value = '{"cake": 5}';
    draft.clearRepeat(store);
    assert(store.value === null, 'clearRepeat удаляет ключ');

    const state = draft.createState([]);
    state.Designed = true;
    state.PdConsent = true;
    state.Words = 'текст';
    draft.resetState(state);
    assert(state.Designed === false && state.PdConsent === false && state.Words === '', 'resetState очищает заказ');
}

testCsrfToken();
testDraft();
testPreview();
testStorage();

if (failed) {
    console.error('\nПРОВАЛЕНО: ' + failed);
    process.exit(1);
}
console.log('\nФРОНТОВЫЕ ПРОВЕРКИ ПРОЙДЕНЫ');
