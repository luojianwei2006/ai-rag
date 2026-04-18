import { defineStore } from 'pinia'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || null,
    userType: localStorage.getItem('userType') || null,
    userInfo: JSON.parse(localStorage.getItem('userInfo') || 'null')
  }),
  actions: {
    setAuth(token, userType, userInfo) {
      this.token = token
      this.userType = userType
      this.userInfo = userInfo
      localStorage.setItem('token', token)
      localStorage.setItem('userType', userType)
      localStorage.setItem('userInfo', JSON.stringify(userInfo))
    },
    logout() {
      this.token = null
      this.userType = null
      this.userInfo = null
      localStorage.removeItem('token')
      localStorage.removeItem('userType')
      localStorage.removeItem('userInfo')
    }
  }
})
