from odoo import models, fields, api

class ReportSickLeaveWizard(models.TransientModel):
    _name = 'report.sick.leave.wizard'
    _description = 'Report Sick Leave to Försäkringskassan'

    # Fälten verkar ok, använder related
    leave_id = fields.Many2one('hr.leave', string='Sick Leave', required=True)
    employee_id = fields.Many2one(related='leave_id.employee_id', string='Employee')
    start_date = fields.Datetime(related='leave_id.date_from', string='Start Date')
    end_date = fields.Datetime(related='leave_id.date_to', string='End Date')
    illness_type = fields.Selection(related='leave_id.illness_type', string='Illness Type')
    report_type = fields.Selection([
        ('initial', 'Initial Report'),
        ('extension', 'Extension'),
        ('termination', 'Early Termination')
    ], string='Report Type', default='initial', required=True)

    def action_generate_report(self):
        self.ensure_one()
        # TODO: Implementation to generate report file
        print(f"Generating FK report for leave {self.leave_id.display_name}, type: {self.report_type}")
        return {'type': 'ir.actions.act_window_close'}