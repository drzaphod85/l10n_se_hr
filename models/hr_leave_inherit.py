
# -*- coding: utf-8 -*-
from odoo import models, fields, api, tools
from odoo.exceptions import ValidationError
from datetime import datetime, date, timedelta
import math

class HrLeaveInherit(models.Model):
    _inherit = 'hr.leave'

    # --- Fält och metoder från hr_vacation_leave_inherit.py ---
    is_swedish_vacation = fields.Boolean(
        string='Swedish Vacation',
        compute='_compute_is_swedish_vacation',
        store=True
    )
    vacation_year = fields.Char(
        string='Vacation Year',
        compute='_compute_vacation_year',
        store=True
    )
    # OBS: vacation_pay_percentage fanns även här i din ursprungliga kod.
    # Om den ska hämtas från leave_type istället, kan denna tas bort.
    # Vi behåller den här för att matcha din ursprungliga kodstruktur.
    vacation_pay_percentage = fields.Float(
        string='Vacation Pay % (Applied)', # Ändrat namn för tydlighet? Eller hämta från type?
        related='holiday_status_id.vacation_pay_percentage', # Förslag: Hämta från typen istället
        store=True, # Eller False om related
        readonly=False # Eller True om related
        # default=12.0 # Behövs inte om related
    )

    @api.depends('holiday_status_id')
    def _compute_is_swedish_vacation(self):
        # Använd raise_if_not_found=False för att undvika fel om ID inte finns vid installation
        swedish_vacation_type = self.env.ref('l10n_se_hr.holiday_status_swedish_vacation', raise_if_not_found=False)
        for leave in self:
            # Kontrollera att swedish_vacation_type faktiskt hittades
            if swedish_vacation_type:
                 leave.is_swedish_vacation = leave.holiday_status_id.id == swedish_vacation_type.id
            else:
                 leave.is_swedish_vacation = False # Sätt default om ref inte hittas

    @api.depends('date_from')
    def _compute_vacation_year(self):
        for leave in self:
            if not leave.date_from:
                leave.vacation_year = ''
                continue
            date_from = leave.date_from # Datetime-objekt direkt i v16+
            year = date_from.year
            month = date_from.month
            if month < 4:
                leave.vacation_year = f"{year-1}/{year}"
            else:
                leave.vacation_year = f"{year}/{year+1}"

    @api.constrains('date_from', 'date_to', 'employee_id', 'holiday_status_id')
    def _check_swedish_vacation_limits(self):
        for leave in self.filtered(lambda l: l.is_swedish_vacation and l.employee_id):
            # Behöver tillgång till employee.remaining_swedish_vacation_days som beräknas i hr.employee
            # Detta kan kräva att beräkningen görs här eller att man litar på den beräknade på employee
            # För enkelhet, låt oss anta att den finns på employee och är uppdaterad:
            # Behöver troligen en @api.depends på number_of_days också
             if leave.number_of_days > leave.employee_id.remaining_swedish_vacation_days:
                 raise ValidationError(f"Employee {leave.employee_id.name} doesn't have enough vacation days ({leave.number_of_days} requested, {leave.employee_id.remaining_swedish_vacation_days} available).")


    # --- Fält och metoder från hr_sick_leave_inherit.py ---
    is_swedish_sick_leave = fields.Boolean(
        string='Swedish Sick Leave',
        compute='_compute_is_swedish_sick_leave',
        store=True
    )
    is_karensdag = fields.Boolean(
        string='Karensavdrag (Qualifying Deduction)', # Uppdaterad term för Odoo 16+?
        help="First day deduction according to Swedish rules",
        compute='_compute_is_karensdag', # Gör denna beräkningsbar
        store=True # Kan behöva store=True om den används i andra beräkningar
    )
    illness_type = fields.Selection([
        ('normal', 'Normal Illness'),
        ('work_injury', 'Work-Related Injury'),
        ('pregnancy', 'Pregnancy-Related'),
        ('contagious', 'Contagious Disease')
    ], string='Illness Type', default='normal')
    doctor_certificate_required = fields.Boolean(
        string='Doctor Certificate Required',
        compute='_compute_doctor_certificate_required',
        store=True # Kan vara bra att lagra detta
    )
    doctor_certificate_provided = fields.Boolean(string='Doctor Certificate Provided')
    sickness_benefit_percentage = fields.Float(string='Sickness Benefit %', default=80.0)
    employer_period = fields.Boolean(
        string="Employer Period",
        help="Within the employer's responsibility period (usually days 1-14)",
        compute='_compute_employer_period',
        store=True # Kan vara bra att lagra
    )
    days_since_last_sick_leave = fields.Integer(
        string='Days Since Last Sick Leave',
        compute='_compute_days_since_last_sick_leave'
        # store=False (behöver nog inte lagras)
    )

    @api.depends('holiday_status_id')
    def _compute_is_swedish_sick_leave(self):
        sick_leave_type = self.env.ref('l10n_se_hr.holiday_status_swedish_sick_leave', raise_if_not_found=False)
        for leave in self:
            if sick_leave_type:
                leave.is_swedish_sick_leave = leave.holiday_status_id.id == sick_leave_type.id
            else:
                leave.is_swedish_sick_leave = False

    @api.depends('number_of_days', 'is_swedish_sick_leave')
    def _compute_doctor_certificate_required(self):
        for leave in self:
            leave.doctor_certificate_required = leave.is_swedish_sick_leave and leave.number_of_days > 7

    @api.depends('date_from', 'number_of_days', 'employee_id', 'is_swedish_sick_leave')
    def _compute_employer_period(self):
        for leave in self:
            if not leave.is_swedish_sick_leave or not leave.date_from or not leave.employee_id:
                leave.employer_period = False
                continue

            date_from = leave.date_from
            # Enklare logik för återinsjuknande (inom 5 dagar) - detta kan behöva förfinas
            five_days_before_start = date_from.date() - timedelta(days=5)

            domain = [
                ('employee_id', '=', leave.employee_id.id),
                ('is_swedish_sick_leave', '=', True),
                ('state', 'in', ['validate', 'validate1']),
                ('date_to', '>=', five_days_before_start), # Slutade inom 5 dagar innan denna startade
                ('id', '!=', leave._origin.id if leave._origin else 0) # Undvik att jämföra med sig själv
            ]
            # Hitta senaste relevanta tidigare period
            previous_relevant_leave = self.env['hr.leave'].search(domain, order='date_to DESC', limit=1)

            if previous_relevant_leave:
                 # Fortsatt sjukperiod, räkna från första dagen i den *sammanhängande* perioden
                 # Behöver potentiellt följa kedjan bakåt... förenklad logik här:
                 first_day_of_period = previous_relevant_leave.date_from # Anta att detta är starten
                 total_days_in_period = (leave.date_to.date() - first_day_of_period.date()).days + 1
                 leave.employer_period = total_days_in_period <= 14
            else:
                 # Ny sjukperiod
                 leave.employer_period = leave.number_of_days <= 14


    @api.depends('date_from', 'employee_id', 'is_swedish_sick_leave')
    def _compute_days_since_last_sick_leave(self):
        for leave in self:
            if not leave.is_swedish_sick_leave or not leave.date_from or not leave.employee_id:
                leave.days_since_last_sick_leave = 999 # Eller None?
                continue

            date_from = leave.date_from
            domain = [
                ('employee_id', '=', leave.employee_id.id),
                ('is_swedish_sick_leave', '=', True),
                ('state', 'in', ['validate', 'validate1']),
                ('date_to', '<', date_from),
                ('id', '!=', leave._origin.id if leave._origin else 0)
            ]
            previous_leave = self.env['hr.leave'].search(domain, order='date_to DESC', limit=1)

            if previous_leave and previous_leave.date_to:
                leave.days_since_last_sick_leave = (date_from.date() - previous_leave.date_to.date()).days
            else:
                leave.days_since_last_sick_leave = 999 # Eller ett stort tal för att indikera ingen föregående

    @api.depends('days_since_last_sick_leave')
    def _compute_is_karensdag(self):
         for leave in self:
              # Karensavdrag görs om det gått mer än 5 dagar sedan föregående sjukperiod slutade
              leave.is_karensdag = leave.days_since_last_sick_leave > 5

    # Onchange to set default percentage, keep this simple for now
    @api.onchange('illness_type', 'is_karensdag')
    def _onchange_sick_leave_percentage(self):
        if self.is_swedish_sick_leave:
            if self.illness_type == 'work_injury':
                self.sickness_benefit_percentage = 100.0
            # Karensavdraget (20% av veckolön) är mer komplicerat än att bara sätta % här.
            # Detta fält representerar nog snarare ersättningsnivån efter avdraget.
            # Så 80% är standard för de flesta dagar.
            else:
                self.sickness_benefit_percentage = 80.0

    @api.constrains('doctor_certificate_required', 'doctor_certificate_provided', 'state')
    def _check_doctor_certificate(self):
        for leave in self.filtered(lambda l: l.is_swedish_sick_leave and l.state == 'validate'): # Check vid validering
            if leave.doctor_certificate_required and not leave.doctor_certificate_provided:
                raise ValidationError(
                    "A doctor's certificate is required for sick leaves longer than 7 days. "
                    "Please attach it or mark it as provided before approving this leave."
                )

    def action_report_sickness_to_fk(self):
        # Logic seems ok, ensure the wizard model exists
        self.ensure_one() # Bra att ha för säkerhets skull
        if self.is_swedish_sick_leave and not self.employer_period:
            return {
                'name': 'Report to Försäkringskassan',
                'type': 'ir.actions.act_window',
                'res_model': 'report.sick.leave.wizard', # Wizard definieras nedan
                'view_mode': 'form',
                'target': 'new',
                'context': {'default_leave_id': self.id}
            }
        else:
            # Kanske visa ett meddelande istället?
             raise UserError("This sick leave is within the employer period or not a Swedish sick leave.")


    # --- Fält och metoder från hr_parental_leave_inherit.py ---
    is_swedish_parental_leave = fields.Boolean(
        string='Swedish Parental Leave',
        compute='_compute_is_swedish_parental_leave',
        store=True
    )
    parental_leave_type = fields.Selection([
        ('pregnancy', 'Pregnancy Leave'),
        ('parental', 'Parental Leave'),
        ('temporary', 'Temporary Parental Leave (VAB)'),
        ('paternity', 'Paternity Leave (10 days)'),
        ('reduced', 'Reduced Working Hours') # Kanske inte en 'leave' på samma sätt?
    ], string='Parental Leave Type', tracking=True) # Added tracking
    fk_case_number = fields.Char(
        string='Försäkringskassan Case Number',
        help='Case number from the Swedish Social Insurance Agency',
        tracking=True
    )
    child_birth_date = fields.Date(string='Child Birth Date', tracking=True)
    child_name = fields.Char(string='Child Name', tracking=True) # Kanske hämta från hr.employee.child?
    child_personnummer = fields.Char(string='Child Personal ID Number', tracking=True) # Kanske hämta?
    benefit_percentage = fields.Selection([
        ('100', '100%'),
        ('75', '75%'),
        ('50', '50%'),
        ('25', '25%'),
        ('12.5', '12.5%')
    ], string='Benefit Percentage', default='100', tracking=True)
    salary_supplement = fields.Boolean(
        string='Salary Supplement',
        help='Employer provides additional compensation on top of Försäkringskassan benefits',
        tracking=True
    )
    supplement_percentage = fields.Float(
        string='Supplement Percentage',
        help='Additional percentage of salary paid by employer',
        tracking=True
    )

    @api.depends('holiday_status_id')
    def _compute_is_swedish_parental_leave(self):
        parental_leave_type = self.env.ref('l10n_se_hr.holiday_status_swedish_parental_leave', raise_if_not_found=False)
        for leave in self:
            if parental_leave_type:
                 leave.is_swedish_parental_leave = leave.holiday_status_id.id == parental_leave_type.id
            else:
                 leave.is_swedish_parental_leave = False

    # Onchange för att sätta defaultvärden, verkar ok
    @api.onchange('parental_leave_type')
    def _onchange_parental_leave_type(self):
        if self.parental_leave_type == 'paternity':
            if self.date_from:
                 # Sätt date_to 10 kalenderdagar framåt
                 date_to = self.date_from + timedelta(days=9) # Inklusive startdagen blir det 10 dagar
                 self.request_date_to = date_to.date() # Sätt request_date_to
                 # Behöver också sätta number_of_days korrekt, Odoo gör detta oftast själv
        elif self.parental_leave_type == 'pregnancy':
            self.benefit_percentage = '100'
        # Lägg till else för att rensa fält om typen ändras tillbaka?

    @api.constrains('parental_leave_type', 'number_of_days')
    def _check_parental_leave_limits(self):
        for leave in self.filtered(lambda l: l.is_swedish_parental_leave):
            if leave.parental_leave_type == 'paternity' and leave.number_of_days > 10:
                raise ValidationError("Paternity leave cannot exceed 10 days according to standard rules.")

    @api.onchange('is_swedish_parental_leave', 'salary_supplement')
    def _onchange_salary_supplement(self):
        # Detta bör nog vara mer konfigurerbart än hårdkodat
        if self.is_swedish_parental_leave and self.salary_supplement:
            self.supplement_percentage = 10.0 # Exempel, bör hämtas från settings/policy
        elif not self.salary_supplement:
             self.supplement_percentage = 0.0 # Nollställ om rutan avmarkeras