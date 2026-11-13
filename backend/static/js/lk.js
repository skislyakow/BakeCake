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
            Schema: {
                name_format: BC.rules.name('⚠ Недопустимые символы в имени', {allowSpaces: true}),
                email_format: BC.rules.email('⚠ Формат почты нарушен')
            }
        }
    },
    async mounted() {
        const me = await api('/api/me/')
        if (!me.ok) {
            window.location.href = '/'
            return
        }
        this.Name = me.name || ''
        this.Phone = me.phone || ''
        this.Email = me.email || ''
    },
    methods: {
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
        async Logout() {
            await BC.logout()
        }
    }
}).mount('#LK')
