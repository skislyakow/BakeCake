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
            Designed: false,
            Catalog: [], CatalogError: '', CatalogOpen: false,
            SelectedCake: null, Levels: null, Form: null, Topping: null,
            Berries: null, Decor: null, Words: '', Comments: '', Promo: '',
            Name: '', Phone: '', Email: '', Address: '', Dates: '', Time: '', DelivComments: '',
            Cost: 0, Quote: null, QuoteError: '', OrderError: '', OrderPlaced: null,
            Submitting: false, RushPercent: 20, ShowPayment: false,
            Groups: [], Sel: {},
        }, {
            schema1: schema1,
            schema2: schema2,
            quoteTimer: null,
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
            return this.Quote && this.Quote.is_rush;
        },
    },
    mounted() {
        this.LoadCatalog();
        this.LoadConfig();
    },
    watch: {
        SelectedCake: 'UpdateQuote',
        Levels: 'UpdateQuote', Topping: 'UpdateQuote', Berries: 'UpdateQuote', Decor: 'UpdateQuote',
        Words: 'UpdateQuote', Promo: 'UpdateQuote', Dates: 'UpdateQuote', Time: 'UpdateQuote',
    },
    methods: {
        Label(code) {
            return BC.draft.labelFor(this, code);
        },
        async LoadCatalog() {
            const data = await api('/api/catalog/');
            if (data.ok) {
                this.Catalog = data.items;
            } else {
                this.CatalogError = firstError(data);
            }
        },
        SelectCake(cake) {
            this.SelectedCake = cake;
            document.getElementById('ToStep3').click();
        },
        ClearCake() {
            this.SelectedCake = null;
            this.UpdateQuote();
        },
        async LoadConfig() {
            const data = await api('/api/cake-config/');
            if (!data.ok) {
                this.ConfigError = firstError(data);
                return;
            }
            this.Groups = data.groups;
            this.Sel = {};
            var self = this;
            this.Groups.forEach(function (g) { self.Sel[g.code] = null; });
            BC.draft.applyConfigDefaults(this, data);

            try {
                var saved = BC.draft.readProfile(localStorage);
                if (saved) {
                    this.Name = saved.name || '';
                    this.Phone = saved.phone || '';
                    this.Email = saved.email || '';
                }
            } catch (e) {}

            this.ApplyRepeat();

            const cakeId = parseInt(new URLSearchParams(location.search).get('cake'), 10);
            if (cakeId && this.Catalog.length === 0) await this.LoadCatalog();
            const fromLink = this.Catalog.find(function (c) { return c.id === cakeId; });
            if (fromLink) this.SelectedCake = fromLink;
        },
        ApplyRepeat() {
            var item = BC.draft.readRepeat(sessionStorage);
            if (!item) return;
            BC.draft.clearRepeat(sessionStorage);
            BC.draft.applyRepeat(this, item);
        },
        ToStep4() {
            this.Designed = true;
            setTimeout(() => this.$refs.ToStep4.click(), 100);
        },
        UpdateQuote() {
            clearTimeout(this.quoteTimer);
            if (!this.Configured || !this.Dates || !this.Time) return;
            this.quoteTimer = setTimeout(() => this.FetchQuote(), 350);
        },
        QuoteBody() {
            return BC.draft.quoteBody(this);
        },
        async FetchQuote() {
            if (!this.Configured) return;
            this.QuoteError = '';
            const data = await api('/api/quote/', 'POST', this.QuoteBody());
            if (data.ok) {
                this.Quote = data;
                this.Cost = data.total;
            } else {
                this.QuoteError = firstError(data);
            }
        },
        async SubmitOrder() {
            this.OrderError = '';
            this.OrderPlaced = null;
            if (!this.Quote) await this.FetchQuote();
            if (!this.Quote) return;

            this.Submitting = true;
            const data = await api('/api/orders/', 'POST', BC.draft.orderBody(this));
            this.Submitting = false;

            if (!data.ok) {
                this.OrderError = firstError(data);
                return;
            }

            try {
                BC.draft.writeProfile(localStorage, {name: this.Name, phone: this.Phone, email: this.Email});
            } catch (e) {}
            this.OrderPlaced = data.number;
            if (data.payment_url) {
                try { localStorage.setItem('bc_paid', JSON.stringify({number: data.number, ts: Date.now()})); } catch (e) {}
                window.location.href = data.payment_url;
            } else {
                window.location.href = '/orders/?order=' + encodeURIComponent(data.number);
            }
            this.ResetForms();
        },
        ResetForms() {
            BC.draft.resetState(this);
            if (this.$refs.PayModal) bootstrap.Modal.getInstance(this.$refs.PayModal).hide();
        },
    },
}).mount('#VueApp');
