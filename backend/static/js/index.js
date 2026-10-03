Vue.createApp({
    name: "App",
    components: {
        VForm: VeeValidate.Form,
        VField: VeeValidate.Field,
        ErrorMessage: VeeValidate.ErrorMessage,
    },
    data() {
        return {
            schema1: {
                lvls: (value) => {
                    if (value) {
                        return true;
                    }
                    return ' количество уровней';
                },
                form: (value) => {
                    if (value) {
                        return true;
                    }
                    return ' форму торта';
                },
                topping: (value) => {
                    if (value) {
                        return true;
                    }
                    return ' топпинг';
                }
            },
            schema2: {
                name: (value) => {
                    if (value) {
                        return true;
                    }
                    return ' имя';
                },
                phone: (value) => {
                    if (value) {
                        return true;
                    }
                    return ' телефон';
                },
                name_format: (value) => {
                    const regex = /^[a-zA-Zа-яА-Я]+$/
                    if (!value) {
                        return true;
                    }
                    if ( !regex.test(value)) {

                        return '⚠ Формат имени нарушен';
                    }
                    return true;
                },
                email_format: (value) => {
                    const regex = /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,4}$/i
                    if (!value) {
                        return true;
                    }
                    if ( !regex.test(value)) {

                        return '⚠ Формат почты нарушен';
                    }
                    return true;
                },
                phone_format:(value) => {
                    const regex = /^((8|\+7)[\- ]?)?(\(?\d{3}\)?[\- ]?)?[\d\- ]{7,10}$/
                    if (!value) {
                        return true;
                    }
                    if ( !regex.test(value)) {

                        return '⚠ Формат телефона нарушен';
                    }
                    return true;
                },
                email: (value) => {
                    if (value) {
                        return true;
                    }
                    return ' почту';
                },
                address: (value) => {
                    if (value) {
                        return true;
                    }
                    return ' адрес';
                },
                date: (value) => {
                    if (value) {
                        return true;
                    }
                    return ' дату доставки';
                },
                time: (value) => {
                    if (value) {
                        return true;
                    }
                    return ' время доставки';
                }
            },
            Config: null,
            ConfigError: '',
            Authed: false,
            Hydrated: false,
            SaveTimer: null,
            Sel: {levels: 0, form: 0, topping: 0, berries: 0, decor: 0},
            Words: '',
            Comments: '',
            Designed: false,
            Quote: null,
            QuoteError: '',
            QuoteTimer: null,
            QuoteTicket: 0,
            Promo: '',
            OrderError: '',
            OrderPlaced: '',

            Name: '',
            Phone: null,
            Email: null,
            Address: null,
            Dates: null,
            Time: null,
            DelivComments: ''
        }
    },
    methods: {
        Label(code) {
            const group = this.Groups.find(g => g.code === code)
            const option = group && group.options.find(o => o.id === this.Sel[code])
            return option ? option.title : 'не выбрано'
        },
        async RequestQuote(body) {
            const ticket = (this.QuoteTicket = (this.QuoteTicket || 0) + 1)
            const data = await api('/api/quote/', 'POST', body)
            if (ticket !== this.QuoteTicket) return // пока шёл запрос, выбор уже поменялся
            if (data.ok) {
                this.Quote = data
            } else {
                this.Quote = null
                this.QuoteError = firstError(data)
            }
        },
async FillProfile() {
            const me = await api('/api/me/')
            if (!me.ok) return
            this.Authed = true
            this.Name = me.name || ''
            this.Phone = me.phone || null
            this.Email = me.email || null
            let address = me.default_address || ''
            if (!address) {
                const orders = await api('/api/orders/')
                if (orders.ok && orders.items && orders.items.length) {
                    address = orders.items[0].address || ''
                }
            }
            this.Address = address || null
        },
        SaveProfile() {
            if (!this.Authed || !this.Hydrated) return
            clearTimeout(this.SaveTimer)
            this.SaveTimer = setTimeout(() => {
                api('/api/me/', 'PATCH', {
                    name: this.Name,
                    email: this.Email,
                    default_address: this.Address
                })
            }, 600)
        },
        async SubmitOrder() {
            const body = {
                spec: {...this.Sel, inscription: this.Words.trim()},
                name: this.Name,
                phone: this.Phone,
                email: this.Email,
                address: this.Address,
                delivery_date: this.Dates,
                delivery_time: this.Time,
                comment: this.Comments,
                courier_comment: this.DelivComments,
                promo_code: this.Promo
            }
            this.OrderError = ''
            this.OrderPlaced = ''
            const data = await api('/api/orders/', 'POST', body)
            if (data.ok) {
                this.OrderPlaced = data.number
            } else {
                this.OrderError = firstError(data)
            }
        },
        ToStep4() {
            this.Designed = true
            setTimeout(() => this.$refs.ToStep4.click(), 0);
        }
    },
    async mounted() {
        const data = await api('/api/configurator/')
        if (!data.ok) {
            this.ConfigError = firstError(data)
            return
        }
        this.Config = data
        await this.FillProfile()
        this.Hydrated = true
    },
    computed: {
        Groups() {
            // имя поля и префикс id берутся из вёрстки макета: levels → lvls / num1, остальные = code
            return this.Config ? this.Config.groups.map(g => ({
                ...g,
                field: g.code === 'levels' ? 'lvls' : g.code,
                prefix: g.code === 'levels' ? 'num' : g.code
            })) : []
        },
        Required() { return this.Groups.filter(g => g.is_required) },
        Extra() { return this.Groups.filter(g => !g.is_required) },
        Preview() {
            // предварительная сумма, пока сервер не может посчитать (нет даты/времени или не всё выбрано)
            if (!this.Config) return 0
            let sum = 0
            for (const g of this.Config.groups) {
                const option = g.options.find(o => o.id === this.Sel[g.code])
                if (option) sum += option.price_delta
            }
            if (this.Words.trim()) sum += this.Config.inscription_price
            return sum
        },
        Cost() {
            return this.Quote ? this.Quote.total : this.Preview
        },
        IsRush() {
            return Boolean(this.Quote && this.Quote.is_rush)
        },
        RushPercent() {
            return this.Config ? this.Config.delivery.rush_surcharge_percent : 0
        },
        QuoteBody() {
            // null, пока серверу нечего считать: он требует все обязательные группы, дату и время
            if (!this.Config || !this.Dates || !this.Time) return null
            if (this.Config.groups.some(g => g.is_required && !this.Sel[g.code])) return null
            return {
                spec: {...this.Sel, inscription: this.Words.trim()},
                delivery_date: this.Dates,
                delivery_time: this.Time,
                promo_code: this.Promo
            }
        }
    },
    watch: {
        Name() {
            this.SaveProfile()
        },
        Email() {
            this.SaveProfile()
        },
        Address() {
            this.SaveProfile()
        },
        QuoteBody: {
            handler(body) {
                clearTimeout(this.QuoteTimer)
                this.Quote = null
                this.QuoteError = ''
                if (!body) return
                this.QuoteTimer = setTimeout(() => this.RequestQuote(body), 250)
            },
            deep: true
        }
    }
}).mount('#VueApp')