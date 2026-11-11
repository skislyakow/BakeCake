Vue.createApp({
    name: "App",
    components: {
        VForm: VeeValidate.Form,
        VField: VeeValidate.Field,
        ErrorMessage: VeeValidate.ErrorMessage,
    },
    data() {
        var draft = (typeof BC !== 'undefined' && BC.draft) ? BC.draft : null;
        var rules = (typeof BC !== 'undefined' && BC.rules) ? BC.rules : null;

        function asValidator(ruleOrFactory, message, fallback) {
            if (!ruleOrFactory) return fallback;
            try {
                var maybe = ruleOrFactory(message);
                return typeof maybe === 'function' ? maybe : ruleOrFactory;
            } catch (e) {
                return typeof ruleOrFactory === 'function' ? ruleOrFactory : fallback;
            }
        }

        var schema1 = draft ? draft.schema1() : {
            lvls: function (value) { return value ? true : ' количество уровней'; },
            form: function (value) { return value ? true : ' форму торта'; },
            topping: function (value) { return value ? true : ' топпинг'; },
        };

        var schema2 = draft ? draft.schema2() : {
            name: function (value) { return value ? true : ' имя'; },
            phone: function (value) { return value ? true : ' телефон'; },
            email: function (value) { return value ? true : ' почту'; },
            address: function (value) { return value ? true : ' адрес'; },
            date: function (value) { return value ? true : ' дату доставки'; },
            time: function (value) { return value ? true : ' время доставки'; },
            name_format: function (value) {
                if (!value) return '⚠ Укажите имя';
                if (!/^[a-zA-Zа-яА-ЯёЁ\s-]+$/.test(value)) return '⚠ Недопустимые символы в имени';
                return true;
            },
            phone_format: function (value) {
                if (!value) return true;
                if (!/^\+?\d[\d\s\-()]{6,}$/.test(value)) return '⚠ Формат телефона нарушен';
                return true;
            },
            email_format: function (value) {
                if (!value) return true;
                if (!/^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,4}$/i.test(value)) return '⚠ Формат почты нарушен';
                return true;
            },
        };

        if (rules) {
            schema2.name_format = asValidator(rules.name, '⚠ Формат имени нарушен', schema2.name_format);
            schema2.phone_format = asValidator(rules.phone, '⚠ Формат телефона нарушен', schema2.phone_format);
            schema2.email_format = asValidator(rules.email, '⚠ Формат почты нарушен', schema2.email_format);
        }

        return Object.assign(draft ? draft.createState([]) : {
            Config: null, ConfigError: '',
            Designed: false,
            Catalog: [], CatalogError: '', CatalogOpen: false,
            SelectedCake: null, Authed: false, Hydrated: false,
            SaveTimer: null, QuoteTimer: null, QuoteTicket: 0,
            Levels: null, Form: null, Topping: null, Berries: null, Decor: null,
            Words: '', Comments: '', Promo: '',
            Name: '', Phone: '', Email: '', Address: '', Dates: '', Time: '', DelivComments: '',
            Quote: null, QuoteError: '', OrderError: '', OrderPlaced: null,
            Submitting: false, RushPercent: 20, ShowPayment: false, PdConsent: false,
            DatesMin: '', TimeFrom: '', TimeTo: '',
            Groups: [], Sel: {},
        }, {
            schema1: schema1,
            schema2: schema2,
        });
    },
    computed: {
        Required() {
            return this.Groups.filter(function (g) { return g.required; });
        },
        Extra() {
            return this.Groups.filter(function (g) { return !g.required; });
        },
        Configured() {
            return BC.draft.isConfigured(this);
        },
        IsRush() {
            return Boolean(this.Quote && this.Quote.is_rush);
        },
        Cost() {
            return BC.draft.previewCost(this);
        },
        QuoteBody() {
            // null, пока серверу нечего считать; иначе тело запроса /api/quote/.
            return BC.draft.quoteBody(this);
        },
        Preview() {
            return BC.draft.previewModel(this);
        },
    },
    async mounted() {
        await Promise.all([this.LoadCatalog(), this.LoadConfig()]);
        this.ApplyRepeat();
        this.ApplyCakeLink();
        await this.LoadProfile();
        this.Hydrated = true;
    },
    watch: {
        Name() {
            this.SaveProfile();
        },
        Email() {
            this.SaveProfile();
        },
        Address() {
            this.SaveProfile();
        },
        QuoteBody: {
            handler(body) {
                clearTimeout(this.QuoteTimer);
                this.Quote = null;
                this.QuoteError = '';
                if (!body) return;
                this.QuoteTimer = setTimeout(() => this.RequestQuote(body), 250);
            },
            deep: true,
        },
    },
    methods: {
        Label(code) {
            return BC.draft.labelFor(this, code);
        },
        ScrollTo(id) {
            const section = document.getElementById(id);
            if (section) section.scrollIntoView();
        },
        ApplyRepeat() {
            // «Повторить заказ» из «Мои заказы» кладёт spec прошлого заказа в sessionStorage.
            var item = BC.draft.readRepeat(sessionStorage);
            if (!item) return;
            BC.draft.clearRepeat(sessionStorage);
            BC.draft.applyRepeat(this, item);
            var target = this.SelectedCake ? 'step4' : 'step3';
            this.$nextTick(() => this.ScrollTo(target));
        },
        ApplyCakeLink() {
            const cakeId = parseInt(new URLSearchParams(location.search).get('cake'), 10);
            if (!cakeId) return;
            const cake = this.Catalog.find(function (c) { return c.id === cakeId; });
            if (cake) this.SelectCake(cake, false);
        },
        async LoadCatalog() {
            const data = await api('/api/catalog/');
            if (!data.ok) {
                this.CatalogError = firstError(data);
                return;
            }
            this.Catalog = data.items || [];
        },
        async LoadConfig() {
            const data = await api('/api/configurator/');
            if (!data.ok) {
                this.ConfigError = firstError(data);
                return;
            }
            BC.draft.applyConfig(this, data);
        },
        SelectCake(cake, scroll = true) {
            this.SelectedCake = cake;
            this.Designed = true;
            this.Quote = null;
            this.QuoteError = '';
            if (scroll) this.$nextTick(() => this.ScrollTo('step4'));
        },
        ClearCake() {
            this.SelectedCake = null;
            this.Quote = null;
            this.QuoteError = '';
            this.$nextTick(() => this.ScrollTo('step3'));
        },
        async LoadProfile() {
            // Вошедшему подставляем данные профиля; гостю оставляем поля пустыми.
            const me = await api('/api/me/');
            if (!me.ok) return;
            this.Authed = true;
            this.Name = me.name || '';
            this.Phone = me.phone || '';
            this.Email = me.email || '';
            let address = me.default_address || '';
            if (!address) {
                const orders = await api('/api/orders/');
                if (orders.ok && orders.items && orders.items.length) {
                    address = orders.items[0].address || '';
                }
            }
            this.Address = address || '';
        },
        SaveProfile() {
            if (!this.Authed || !this.Hydrated) return;
            clearTimeout(this.SaveTimer);
            this.SaveTimer = setTimeout(() => {
                api('/api/me/', 'PATCH', {
                    name: this.Name,
                    email: this.Email,
                    default_address: this.Address,
                });
            }, 600);
        },
        ToStep4() {
            this.SelectedCake = null;
            this.Quote = null;
            this.QuoteError = '';
            this.Designed = true;
            this.$nextTick(() => this.ScrollTo('step4'));
        },
        async RequestQuote(body) {
            const ticket = (this.QuoteTicket = (this.QuoteTicket || 0) + 1);
            const data = await api('/api/quote/', 'POST', body);
            if (ticket !== this.QuoteTicket) return; // пока шёл запрос, выбор уже поменялся
            if (data.ok) {
                this.Quote = data;
            } else {
                this.Quote = null;
                this.QuoteError = firstError(data);
            }
        },
        async SubmitOrder() {
            if (this.Submitting) return;
            this.OrderError = '';
            this.OrderPlaced = null;
            if (!this.PdConsent) {
                this.OrderError = 'Подтвердите согласие на обработку персональных данных';
                return;
            }

            this.Submitting = true;
            try {
                const data = await api('/api/orders/', 'POST', BC.draft.orderBody(this));
                if (!data.ok) {
                    this.OrderError = firstError(data);
                    return;
                }

                this.ResetForms();
                this.OrderPlaced = data.number;

                if (data.order_id) {
                    const pay = await api('/api/payments/' + data.order_id + '/', 'POST');
                    if (pay.ok && pay.confirmation_url) {
                        window.location.href = pay.confirmation_url;
                        return;
                    }
                }
                // Платёж не создался — заказ уже принят, покажем его в «Моих заказах».
                window.location.href = '/orders/?order=' + encodeURIComponent(data.number);
            } finally {
                this.Submitting = false;
            }
        },
        ResetForms() {
            clearTimeout(this.SaveTimer);
            clearTimeout(this.QuoteTimer);
            this.Hydrated = false;
            BC.draft.resetState(this);
            if (this.Authed) {
                this.LoadProfile().finally(() => {
                    this.Hydrated = true;
                });
            } else {
                this.Hydrated = true;
            }
        },
    },
}).mount('#VueApp');
