import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import * as icons from '@element-plus/icons-vue'
import 'element-plus/dist/index.css'
import './style.scss'
import App from './App.vue'
import router from './router'

const app = createApp(App)
for (const [name, component] of Object.entries(icons)) app.component(name, component)
app.use(ElementPlus, { locale: zhCn }).use(router).mount('#app')
