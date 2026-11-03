<template>
  <el-form-item label="关联模板">
    <div class="template-choice"><el-select :model-value="modelValue || undefined" filterable remote clearable :remote-method="search" :loading="loading" placeholder="选择一个模板（可选）" aria-label="技能关联模板" @update:model-value="emit('update:modelValue',$event || null)" @visible-change="visibleChange"><el-option v-for="item in options" :key="item.id" :label="item.skillName" :value="item.id" :disabled="item.status==='deleting'" /></el-select><el-alert v-if="error" :title="error" type="warning" :closable="false"><template #default><el-button link @click="load">重新加载</el-button></template></el-alert><small>每个技能最多关联一个模板；同一模板可以供多个技能使用。</small></div>
  </el-form-item>
</template>
<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { getCompanyTemplate,getCompanyTemplates,type CompanyTemplate } from '@/api/skill'
const props=defineProps<{modelValue?:string|null;open:boolean}>()
const emit=defineEmits<{'update:modelValue':[string|null];ready:[boolean]}>()
const options=ref<CompanyTemplate[]>([]),loading=ref(false),error=ref('')
let keyword='',version=0,disposed=false,timer:ReturnType<typeof setTimeout>|undefined
async function load(){const request=++version;loading.value=true;error.value='';emit('ready',false)
  try{const res=await getCompanyTemplates({keyword,pageNo:1,pageSize:100});if(!res.success)throw new Error(res.message||'模板列表加载失败');let rows=res.data.list
    if(props.modelValue&&!rows.some(row=>row.id===props.modelValue)){const detail=await getCompanyTemplate(props.modelValue);if(!detail.success)throw new Error('已绑定模板不可用，请清除或重新选择');rows=[detail.data.meta,...rows]}
    if(request===version&&!disposed){options.value=rows;emit('ready',true)}
  }catch(cause){if(request===version&&!disposed){error.value=cause instanceof Error?cause.message:'模板加载失败';emit('ready',!props.modelValue)}}finally{if(request===version)loading.value=false}
}
function search(value:string){keyword=value;clearTimeout(timer);timer=setTimeout(()=>void load(),250)}
function visibleChange(visible:boolean){if(visible)void load()}
watch(()=>props.open,open=>{if(open){keyword='';void load()}else{++version;clearTimeout(timer)}},{immediate:true})
watch(()=>props.modelValue,value=>{if(!value&&error.value)emit('ready',true)})
onBeforeUnmount(()=>{disposed=true;++version;clearTimeout(timer)})
</script>
<style scoped>.template-choice{width:100%}.el-select{width:100%}small{display:block;color:var(--el-text-color-secondary);line-height:1.6}.el-alert{margin-top:8px}</style>
