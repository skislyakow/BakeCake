Vue.createApp({
    data() {
        return {
            Orders: [],
            OrdersLoaded: false,
            OrdersError: '',
            Detail: {},       // number → полный ответ GET /api/orders/<number>/ (подгружается при открытии карточки)
            Issue: {},        // number → состояние формы жалобы
            Repeating: '',
            RepeatError: '',
            Paid: new URLSearchParams(location.search).get('paid') === '1',
        }
    },
    async mounted() {
        document.addEventListener('show.bs.modal', (event) => {
            const number = event.target && event.target.dataset ? event.target.dataset.number : null
            if (number) this.LoadDetail(number)
        })
        const data = await api('/api/orders/')
        if (!data.ok) {
            if (data.errors && data.errors.auth) {
                window.location.href = '/'  // сессия закончилась
                return
            }
            this.OrdersError = firstError(data)
        } else {
            this.Orders = data.items
            for (const o of data.items) {
                this.Issue[o.number] = {open: false, text: '', sending: false, done: false, error: ''}
            }
        }
        this.OrdersLoaded = true
        this.HandleReturn()
    },
    methods: {
        HandleReturn() {
            // возврат с оплаты: открыть карточку заказа и дождаться вебхука (план, раздел 7)
            const number = new URLSearchParams(location.search).get('order')
            if (!number) return
            const el = document.getElementById('OrderModal' + number)
            if (el) {
                bootstrap.Modal.getOrCreateInstance(el).show()
                if (this.Paid) this.PollUntilPaid(number)
            }
        },
        async PollUntilPaid(number) {
            // статус меняет только вебхук, даём ему время
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
}).mount('#Orders')