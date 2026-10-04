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
        const me = await api('/api/me/')
        if (!me.ok) {
            window.location.href = '/'  // сессия закончилась
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
            const data = await api('/api/auth/logout/', 'POST')
            if (data.ok) window.location.href = '/'
        }
    }
}).mount('#LK')