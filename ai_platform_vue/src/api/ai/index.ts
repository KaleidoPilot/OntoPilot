import request from '@/util/request';

export function getQuickActions() {
  return request({
    url: '/ai/quick-actions/list',
    method: 'GET'
  });
}

export function saveQuickActions(data: { actions: any[] }) {
  return request({
    url: '/ai/quick-actions/save',
    method: 'POST',
    data
  });
}
