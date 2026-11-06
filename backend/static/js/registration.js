Vue.createApp({
    components: {
        VForm: VeeValidate.Form,
        VField: VeeValidate.Field,
        ErrorMessage: VeeValidate.ErrorMessage,
    },
    data() {
        return {
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
            Loading: false
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
                this.Step = 'Code'
                this.EnteredNumber = this.RegInput
                this.RegInput = ''
                return
            }
            if (this.Step === 'Code') {
                if (this.Loading) return
                this.Loading = true
                const data = await api('/api/auth/login/', 'POST', {
                    phone: this.EnteredNumber,
                    last4: this.RegInput,
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
                this.Step = 'Finish'
                this.RegInput = 'Регистрация успешна'
                // перезагрузка: шапка рисуется на сервере, а csrf-токен меняется при входе
                setTimeout(() => window.location.reload(), 800)
            }
        },
        ToRegStep1() {
            this.Step = 'Number'
            this.RegInput = this.EnteredNumber
        },
        Reset() {
            this.Step = 'Number'
            this.RegInput = ''
            this.EnteredNumber = ''
            this.ApiError = ''
        }
    }
}).mount('#RegModal')