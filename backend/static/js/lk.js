Vue.createApp({
    components: {
        VForm: VeeValidate.Form,
        VField: VeeValidate.Field,
        ErrorMessage: VeeValidate.ErrorMessage,
    },
    data() {
        return {
            Edit: false,
            Saving: false,
            ApiError: '',
            Name: '',
            Phone: '',
            Email: '',
            Orders: [],
            OrdersLoaded: false,
            OrdersError: '',
            Detail: {},       // number → полный ответ GET /api/orders/<number>/ (подгружается при открытии карточки)
            Issue: {},        // number → состояние формы жалобы
            Repeating: '',
            RepeatError: '',
            Schema: {
                // пустые имя и почта допустимы: после входа по телефону профиль создаётся без них
                name_format: (value) => {
                    if (!value) {
                        return true;
                    }
                    if (!/^[a-zA-Zа-яА-ЯёЁ\s-]+$/.test(value)) {
                        return '⚠ Недопустимые символы в имени';
                    }
                    return true;
                },
                email_format: (value) => {
                    if (!value) {
                        return true;
                    }
                    if (!/^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,4}$/i.test(value)) {
                        return '⚠ Формат почты нарушен';
                    }
                    return true;
                }
            }
        }
    },
    async mounted() {
        document.addEventListener('show.bs.modal', (event) => {
            const number = event.target && event.target.dataset ? event.target.dataset.number : null
            if (number) this.LoadDetail(number)
        })
        const [me, orders] = await Promise.all([api('/api/me/'), api('/api/orders/')])
        if (!me.ok) {
            window.location.href = '/'  // сессия закончилась
            return
        }
        this.Name = me.name || ''
        this.Phone = me.phone || ''
        this.Email = me.email || ''
        if (orders.ok) {
            this.Orders = orders.items
            for (const o of orders.items) {
                this.Issue[o.number] = {open: false, text: '', sending: false, done: false, error: ''}
            }
        } else {
            this.OrdersError = firstError(orders)
        }
        this.OrdersLoaded = true
        this.HandleReturn()
    },
    methods: {
        HandleReturn() {
            const params = new URLSearchParams(location.search)
            const number = params.get('order')
            if (!number) return
            const el = document.getElementById('OrderModal' + number)
            if (el) {
                bootstrap.Modal.getOrCreateInstance(el).show()
                if (params.get('paid') === '1') this.PollUntilPaid(number)
            }
        },
        async PollUntilPaid(number) {
            // возврат с оплаты: статус меняет только вебхук, даём ему время (план, раздел 7)
            for (let i = 0; i < 4; i++) {
                await new Promise(r => setTimeout(r, 1500))
                delete this.Detail[number]
                const detail = await this.LoadDetail(number)
                const order = this.Orders.find(o => o.number === number)
                if (detail && detail.status === 'paid') {
                    if (order) order.status = detail.status
                    return
                }
            }
        },
        async ApplyChanges() {
            this.ApiError = ''
            this.Saving = true
            const data = await api('/api/me/', 'PATCH', {name: (this.Name || '').trim(), email: (this.Email || '').trim()})
            this.Saving = false
            if (!data.ok) {
                this.ApiError = firstError(data)
                return
            }
            this.Name = data.name || ''
            this.Email = data.email || ''
            this.Edit = false
        },
        MonthDay(order) {
            const [y, m, d] = order.delivery_date.split('-').map(Number)
            return new Date(y, m - 1, d).toLocaleDateString('ru-RU', {day: 'numeric', month: 'long'})
        },
        ShortDate(order) {
            return this.MonthDay(order)
        },
        DeliveryText(order) {
            return this.MonthDay(order) + ', ' + order.delivery_time
        },
        async LoadDetail(number) {
            if (this.Detail[number]) return this.Detail[number]
            const data = await api('/api/orders/' + encodeURIComponent(number) + '/')
            if (data.ok) this.Detail[number] = data
            return this.Detail[number] || null
        },
        async RepeatOrder(number) {
            this.RepeatError = ''
            this.Repeating = number
            const detail = await this.LoadDetail(number)
            this.Repeating = ''
            if (!detail) {
                this.RepeatError = 'Не удалось загрузить заказ, попробуйте ещё раз'
                return
            }
            try {
                sessionStorage.setItem('bc_repeat', JSON.stringify(detail.spec))
            } catch (e) {
                this.RepeatError = 'Браузер не дал сохранить заказ, соберите торт заново'
                return
            }
            window.location.href = '/#step3'
        },
        async SendIssue(number) {
            const form = this.Issue[number]
            form.error = ''
            if (!form.text.trim()) {
                form.error = '⚠ Напишите, что случилось'
                return
            }
            form.sending = true
            const data = await api('/api/orders/' + encodeURIComponent(number) + '/issue/', 'POST', {message: form.text.trim()})
            form.sending = false
            if (!data.ok) {
                form.error = firstError(data)
                return
            }
            form.done = true
            form.open = false
            form.text = ''
        },
        async Logout() {
            const data = await api('/api/auth/logout/', 'POST')
            if (data.ok) window.location.href = '/'
        }
    }
}).mount('#LK')
