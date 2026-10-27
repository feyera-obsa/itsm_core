frappe.listview_settings["Grafana Webhook Log"] = {
  onload(listview) {
    listview.page.add_inner_button(__("API Docs"), () => {
      window.open("/assets/itsm_core/scalar_docs.html", "_blank", "noopener");
    });
  },
};