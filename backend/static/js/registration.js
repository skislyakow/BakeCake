Vue.createApp({
    components: {
        VForm: VeeValidate.Form,
        VField: VeeValidate.Field,
        ErrorMessage: VeeValidate.ErrorMessage,
    },
    data() {
        const root = document.getElementById('RegModal');
        return {
            AuthMode: (root && root.dataset.authMode) || 'demo',
            RegSchema: {
                reg: BC.rules.required('Поле не заполнено'),
                phone_format: BC.rules.phone('⚠ Формат телефона нарушен'),
                code_format: BC.rules.code('⚠ Формат кода нарушен')
            },
            Step: 'Number',
            RegInput: '',
            EnteredNumber: '',
            Consent: false,
            ApiError: '',
            Loading: false,
            CallNumber: '',
            CallToken: '',
            CallExpiresIn: 0,
            CallLeft: 0,
            PollTimer: null,
            PollTicks: 0,
            Polling: false
        }
    },
    computed: {
        CallTimeLabel() {
            const minutes = String(Math.floor(this.CallLeft / 60)).padStart(2, '0')
            const seconds = String(this.CallLeft % 60).padStart(2, '0')
            return minutes + ':' + seconds
        }
    },
    watch: {
        RegInput() { this.ApiError = '' },
        Consent() { this.ApiError = '' }
    },
    methods: {
        async RegSubmit() {
            this.ApiError = ''
            if (this.Step === 'Number') {
                if (!this.Consent) {
                    this.ApiError = 'Необходимо согласие на обработку персональных данных'
                    return
                }
                this.EnteredNumber = this.RegInput
                if (this.AuthMode === 'demo') {
                    this.Step = 'Code'
                    this.RegInput = ''
                    return
                }
                await this.RequestLogin()
                return
            }
            if (this.Step === 'Code') {
                await this.RequestLogin()
            }
        },
        async RequestLogin() {
            if (this.Loading) return
            this.Loading = true
            const data = await api('/api/auth/login/', 'POST', {
                phone: this.EnteredNumber,
                last4: this.Step === 'Code' ? this.RegInput : '',
                consent_pdp: this.Consent
            })
            this.Loading = false
            if (!data.ok) {
                const message = firstError(data)
                if (data.errors && data.errors.phone) {
                    this.ToRegStep1()
                }
                this.$nextTick(() => { this.ApiError = message })
                return
            }
            if (data.status === 'pending') {
                this.StartCall(data)
                return
            }
            this.Finish()
        },
        Finish() {
            this.StopPolling()
            this.Step = 'Finish'
            this.RegInput = 'Регистрация успешна'

            setTimeout(() => window.location.reload(), 800)
        },
        StartCall(data) {
            this.Step = 'Call'
            this.RegInput = ''
            this.CallNumber = data.number || ''
            this.CallToken = data.token || ''
            this.CallExpiresIn = Number(data.expires_in) || 0
            this.CallLeft = this.CallExpiresIn
            this.StartPolling()
        },
        StartPolling() {
            this.StopPolling()
            this.PollTicks = 0
            this.PollTimer = setInterval(() => {
                this.CallLeft = Math.max(0, this.CallLeft - 1)
                this.PollTicks += 1
                if (this.CallLeft === 0 || this.PollTicks % 2 === 0) {
                    this.PollStatus()
                }
            }, 1000)
        },
        StopPolling() {
            if (this.PollTimer) {
                clearInterval(this.PollTimer)
                this.PollTimer = null
            }
        },
        async PollStatus() {
            if (this.Polling || !this.CallToken) return
            this.Polling = true
            const data = await api('/api/auth/verify/status/?token=' + encodeURIComponent(this.CallToken))
            this.Polling = false
            if (!data || !data.ok) return
            if (data.status === 'confirmed') {
                this.Finish()
                return
            }
            if (data.status === 'expired' || data.status === 'rejected') {
                this.StopPolling()
                this.ApiError = data.status === 'expired'
                    ? 'Время ожидания истекло, попробуйте ещё раз'
                    : 'Звонок не подтверждён, попробуйте ещё раз'
                this.ToRegStep1()
            }
        },
        ToRegStep1() {
            this.StopPolling()
            this.Step = 'Number'
            this.RegInput = this.EnteredNumber
            this.CallToken = ''
            this.CallNumber = ''
            this.CallLeft = 0
        },
        Reset() {
            this.StopPolling()
            this.Step = 'Number'
            this.RegInput = ''
            this.EnteredNumber = ''
            this.ApiError = ''
            this.CallToken = ''
            this.CallNumber = ''
            this.CallLeft = 0
        }
    }
}).mount('#RegModal')
