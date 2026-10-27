// itsm_core/client_script/grafana_webhook_log_list.js

frappe.provide('frappe.listview_settings');

frappe.listview_settings['Grafana Webhook Log'] = {
    onload: function(listview) {
        console.log('=== Client Script Loaded: Grafana Webhook Log ===');
        console.log('listview:', listview);
        console.log('listview.page:', listview.page);
        console.log('listview.page.add_primary_action:', listview.page && listview.page.add_primary_action);
        
        if (listview.page && listview.page.add_primary_action) {
            listview.page.add_primary_action('API Documentation', function() {
                window.open('/assets/itsm_core/scalar_docs.html', '_blank');
            });
            console.log('API Documentation button added successfully');
        } else {
            console.log('ERROR: page or add_primary_action not available');
            console.log('listview.page:', listview.page);
            if (listview.page) {
                console.log('listview.page.add_primary_action:', listview.page.add_primary_action);
            }
        }
    }
};