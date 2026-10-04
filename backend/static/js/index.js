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
            Catalog: [],
            CatalogError: '',
            CatalogOpen: false,
            SelectedCake: null,
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
            Submitting: false,

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
        ApplyRepeat() {
            // «Повторить заказ» из «Мои заказы» кладёт spec прошлого заказа в sessionStorage (orders.js)
            let spec = null
            try {
                const raw = sessionStorage.getItem('bc_repeat')
                sessionStorage.removeItem('bc_repeat')
                spec = raw ? JSON.parse(raw) : null
            } catch (e) {
                return
            }
            if (!spec || typeof spec !== 'object') return
            if (typeof spec.cake === 'number') {
                const cake = this.Catalog.find(c => c.id === spec.cake)
                if (cake) {
                    this.SelectCake(cake, false)
                    this.$nextTick(() => {
                        const section = document.getElementById('step4')
                        if (section) section.scrollIntoView()
                    })
                }
                return
            }
            for (const g of this.Config.groups) {
                // опция могла исчезнуть из каталога с тех пор — тогда группу не трогаем
                if (g.options.some(o => o.id === spec[g.code])) this.Sel[g.code] = spec[g.code]
            }
            if (typeof spec.inscription === 'string') this.Words = spec.inscription
            this.$nextTick(() => {
                const section = document.getElementById('step3')
                if (section) section.scrollIntoView()
            })
        },
        async LoadCatalog() {
            const data = await api('/api/catalog/')
            if (!data.ok) {
                this.CatalogError = firstError(data)
                return
            }
            this.Catalog = data.items || []
        },
        SelectCake(cake, scroll = true) {
            this.SelectedCake = cake
            this.Designed = true
            this.Quote = null
            this.QuoteError = ''
            if (scroll) {
                this.$nextTick(() => {
                    const section = document.getElementById('step4')
                    if (section) section.scrollIntoView()
                })
            }
        },
        ClearCake() {
            this.SelectedCake = null
            this.Quote = null
            this.QuoteError = ''
            this.$nextTick(() => {
                const section = document.getElementById('step3')
                if (section) section.scrollIntoView()
            })
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
            if (this.Submitting) return
            this.Submitting = true
            this.OrderError = ''
            this.OrderPlaced = ''
            try {
                const payload = {
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
                if (this.SelectedCake) {
                    payload.cake_id = this.SelectedCake.id
                } else {
                    payload.spec = {...this.Sel, inscription: this.Words.trim()}
                }
                const data = await api('/api/orders/', 'POST', payload)
                if (data.ok) {
                    this.OrderPlaced = data.number
                    this.ResetForms()
                    try {
                        const pay = await api(`/api/payments/${data.order_id}/`, 'POST')
                        if (pay.ok && pay.confirmation_url) {
                            window.location.href = pay.confirmation_url
                        }
                    } catch (e) {
                        // платёж не удалось создать — заказ принят, оплатить можно позже в ЛК
                    }
                } else {
                    this.OrderError = firstError(data)
                }
            } finally {
                this.Submitting = false
            }
        },
        ResetForms() {
            clearTimeout(this.SaveTimer)
            this.Hydrated = false
            this.Sel = {levels: 0, form: 0, topping: 0, berries: 0, decor: 0}
            this.Words = ''
            this.Comments = ''
            this.DelivComments = ''
            this.Promo = ''
            this.Quote = null
            this.QuoteError = ''
            this.SelectedCake = null
            this.CatalogOpen = false
            this.Dates = null
            this.Time = null
            this.Name = ''
            this.Phone = null
            this.Email = null
            this.Address = null
            if (this.Authed) {
                this.FillProfile().finally(() => {
                    this.Hydrated = true
                })
            } else {
                this.Hydrated = true
            }
        },
        ToStep4() {
            this.SelectedCake = null
            this.Quote = null
            this.QuoteError = ''
            this.Designed = true
            setTimeout(() => this.$refs.ToStep4.click(), 0)
        }
    },
    async mounted() {
        await Promise.all([this.LoadCatalog(), this._loadConfigurator()])
        this.ApplyRepeat()
        await this.FillProfile()
        this.Hydrated = true
    },
    async _loadConfigurator() {
        const data = await api('/api/configurator/')
        if (!data.ok) {
            this.ConfigError = firstError(data)
            return
        }
        this.Config = data
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
            if (this.Quote) return this.Quote.total
            if (this.SelectedCake) return this.SelectedCake.price
            return this.Preview
        },
        IsRush() {
            return Boolean(this.Quote && this.Quote.is_rush)
        },
        RushPercent() {
            return this.Config ? this.Config.delivery.rush_surcharge_percent : 0
        },
        QuoteBody() {
            // null, пока серверу нечего считать: для готового торта нужны дата и время,
            // для своего — ещё и все обязательные группы
            if (!this.Dates || !this.Time) return null
            if (this.SelectedCake) {
                return {
                    cake_id: this.SelectedCake.id,
                    delivery_date: this.Dates,
                    delivery_time: this.Time,
                    promo_code: this.Promo
                }
            }
            if (!this.Config || this.Config.groups.some(g => g.is_required && !this.Sel[g.code])) return null
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