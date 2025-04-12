# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import date, timedelta

class HrEmployeeInherit(models.Model):
    _inherit = 'hr.employee'

    # --- Fält och metoder från hr_vacation_leave_inherit.py ---
    swedish_vacation_days = fields.Float(
        string='Annual Vacation Days Entitlement', # Tydligare namn?
        default=25.0,
        tracking=True,
        help='Standard is 25 days according to law, can be higher based on collective agreements'
    )
    remaining_swedish_vacation_days = fields.Float(
        string='Remaining Vacation Days (Current Year)', # Tydligare namn?
        compute='_compute_remaining_swedish_vacation_days',
        help="Calculated based on validated allocations and leaves for the current vacation year."
    )
    vacation_salary_base = fields.Monetary(
        string='Vacation Salary Base (Earning Year)', # Tydligare namn?
        currency_field='company_currency',
        tracking=True,
        help='Base amount for calculating vacation pay, typically based on previous earning year salary.'
    )
    company_currency = fields.Many2one( # Behövs denna explicit? Finns via company_id
        'res.currency',
        string='Company Currency',
        related='company_id.currency_id',
        readonly=True
    )
    accrued_vacation_pay = fields.Monetary(
        string='Accrued Vacation Pay (Semesterlön)', # Tydligare namn?
        currency_field='company_currency',
        compute='_compute_accrued_vacation_pay',
        help="Calculated potential vacation pay based on base and percentage (e.g., 12%)."
    )

    overtime_count = fields.Integer(
        string='Overtime Records', 
        compute='_compute_overtime_stats'
    )
    overtime_hours = fields.Float(
        string='Total Overtime Hours',
        compute='_compute_overtime_stats'
    )
    
    def _compute_overtime_stats(self):
        """Compute overtime statistics for employee"""
        Overtime = self.env['hr.overtime.swedish']
        for employee in self:
            domain = [
                ('employee_id', '=', employee.id),
                ('state', 'in', ['approved', 'paid'])
            ]
            
            overtime_records = Overtime.search(domain)
            employee.overtime_count = len(overtime_records)
            employee.overtime_hours = sum(overtime_records.mapped('duration'))

    # Compute-metod för återstående dagar
    def _compute_remaining_swedish_vacation_days(self):
        # Denna metod behöver vara robust och hantera fall där ref inte finns
        swedish_vacation_type = self.env.ref('l10n_se_hr.holiday_status_swedish_vacation', raise_if_not_found=False)
        if not swedish_vacation_type:
            for employee in self:
                employee.remaining_swedish_vacation_days = 0.0
            return

        # Bestäm innevarande semesterår
        today = fields.Date.today()
        year = today.year
        month = today.month
        if month < 4:
            vacation_year = f"{year-1}/{year}"
            # För att söka i allocation/leave, behöver vi start/slutdatum för året
            # OBS: Datum i allocation/leave är inte alltid kopplade till semesterår i standard Odoo
            # Detta kan kräva att vi söker baserat på leave.vacation_year eller allocation.vacation_year om de finns
            # Eller filtrera på date_from/date_to för perioden
            start_date = date(year - 1, 4, 1)
            end_date = date(year, 3, 31)
        else:
            vacation_year = f"{year}/{year+1}"
            start_date = date(year, 4, 1)
            end_date = date(year + 1, 3, 31)

        # Hämta alla anställdas ID:n
        employee_ids = self.ids
        if not employee_ids:
            return

        # Läs data för alla anställda samtidigt för bättre prestanda
        allocation_data = self.env['hr.leave.allocation'].read_group(
             [('employee_id', 'in', employee_ids),
              ('holiday_status_id', '=', swedish_vacation_type.id),
              ('state', '=', 'validate'),
              # Filtrera på datum istället för 'vacation_year'-fältet om det inte är tillförlitligt
              # ('date_from', '<=', end_date), # Behöver mer komplex logik för att matcha år
             ],
             ['employee_id', 'number_of_days:sum'], ['employee_id'])

        leave_data = self.env['hr.leave'].read_group(
             [('employee_id', 'in', employee_ids),
              ('holiday_status_id', '=', swedish_vacation_type.id),
              ('state', 'in', ['validate', 'validate1']),
              ('date_from', '>=', start_date), # Ledighet tagen under semesteråret
              ('date_from', '<=', end_date)
             ],
             ['employee_id', 'number_of_days:sum'], ['employee_id'])

        # Mappa resultat till dictionary för snabb lookup
        alloc_map = {data['employee_id'][0]: data['number_of_days'] for data in allocation_data}
        leave_map = {data['employee_id'][0]: data['number_of_days'] for data in leave_data}

        for employee in self:
             # TODO: Förfina allocated_days - bör nog baseras på intjänad rätt snarare än bara allocation?
             # Detta är en förenkling. Korrekt beräkning kräver intjänanderegler.
             allocated_days = alloc_map.get(employee.id, 0.0)
             used_days = leave_map.get(employee.id, 0.0)
             # Återstående kan inte vara negativt om inte 'allows_negative' är satt på typen
             remaining = allocated_days - used_days
             employee.remaining_swedish_vacation_days = remaining # Kan bli negativt om tillåtet

    # Compute-metod för semesterlön
    def _compute_accrued_vacation_pay(self):
        for employee in self:
            # TODO: Denna beräkning är väldigt förenklad. Verklig semesterlön baseras
            # på intjänandeårets inkomst enligt procent- eller sammalöneregeln.
            # Detta kräver integration med lönesystemet (payslips).
            # 'vacation_salary_base' behöver definieras och populeras.
            base = employee.vacation_salary_base or 0.0
            # Hämta % från leave_type eller en generell inställning?
            # Antag att vi använder en standard 12% om inget annat anges.
            percentage = employee.company_id.default_vacation_pay_percentage or 12.0 # Exempel på inställning
            employee.accrued_vacation_pay = base * (percentage / 100.0)

    # Modell-metoder (från hr_vacation_leave_inherit.py)
    @api.model
    def calculate_vacation_days_earned(self, date_start, date_end, employee_id):
        # Denna logik behöver ses över mot Semesterlagen.
        # Intjänande är komplext (anställningstid, sysselsättningsgrad etc.)
        # Förenklad version:
        employee = self.browse(employee_id)
        if not employee or not date_start or not date_end:
            return 0.0

        # Antag 2.08 dagar per månad vid heltid
        months_employed_in_period = 12 # Förenkling - behöver räknas ut baserat på anst.tid under perioden
        earned = months_employed_in_period * (employee.swedish_vacation_days / 12)
        return earned

    @api.model
    def allocate_annual_vacation(self):
        # Denna metod verkar rimlig för att skapa en årlig allokering
        swedish_vacation_type = self.env.ref('l10n_se_hr.holiday_status_swedish_vacation', raise_if_not_found=False)
        if not swedish_vacation_type:
            # Logga ett fel eller varna
            print("ERROR: Swedish vacation leave type not found (l10n_se_hr.holiday_status_swedish_vacation)")
            return False

        today = fields.Date.today()
        # Ska köras 1:a april för nästa semesterår
        if today.month == 4 and today.day == 1:
             vacation_year_start_date = date(today.year, 4, 1)
             vacation_year_end_date = date(today.year + 1, 3, 31)
             vacation_year_str = f"{today.year}/{today.year+1}"

             employees = self.search([('active', '=', True)]) # Hitta alla aktiva anställda
             allocation_vals_list = []
             for employee in employees:
                  # TODO: Beräkna intjänade dagar baserat på föregående år istället för default?
                  days_to_allocate = employee.swedish_vacation_days # Använder default rätt

                  allocation_vals_list.append({
                      'name': f'Annual Vacation Allocation {vacation_year_str} for {employee.name}',
                      'holiday_status_id': swedish_vacation_type.id,
                      'employee_id': employee.id,
                      'number_of_days': days_to_allocate,
                      'state': 'confirm', # Starta som 'confirm', låt valideras manuellt/automatiskt
                      'date_from': vacation_year_start_date, # Sätt giltighetstid?
                      # 'date_to': vacation_year_end_date, # Odoo sätter ofta inte date_to på allocation
                      # Lägg till vacation_year på allocation om det fältet finns
                      'vacation_year': vacation_year_str, # Om fältet finns på hr.leave.allocation
                  })
             if allocation_vals_list:
                  allocations = self.env['hr.leave.allocation'].create(allocation_vals_list)
                  # Valfritt: försök validera automatiskt
                  # allocations.action_validate()
                  print(f"Created {len(allocations)} annual vacation allocations for {vacation_year_str}")
                  return True
        return False

    # --- Fält och metoder från hr_sick_leave_inherit.py ---
    sick_leave_counter = fields.Integer(
        string='Sick Leave Count (Last 12 months)',
        compute='_compute_sick_leave_statistics'
    )
    sick_leave_days = fields.Float( # Ändrat till Float för att matcha number_of_days
        string='Sick Leave Days (Last 12 months)',
        compute='_compute_sick_leave_statistics'
    )
    frequently_ill = fields.Boolean(
        string='Frequently Ill (Rehab Needed?)', # Tydligare text
        compute='_compute_sick_leave_statistics',
        help='Employee has been on sick leave more than 6 times in the last 12 months, may indicate need for rehabilitation efforts.'
    )

    def _compute_sick_leave_statistics(self):
        # Denna beräkning verkar rimlig
        today = fields.Date.today()
        # Använd relativedelta för exakt 12 månader? Eller är 365 dagar ok?
        date_12_months_ago = today - timedelta(days=365)

        sick_leave_type = self.env.ref('l10n_se_hr.holiday_status_swedish_sick_leave', raise_if_not_found=False)
        if not sick_leave_type:
             for employee in self:
                 employee.sick_leave_counter = 0
                 employee.sick_leave_days = 0.0
                 employee.frequently_ill = False
             return

        employee_ids = self.ids
        if not employee_ids:
            return

        # Hämta data för alla anställda samtidigt
        leave_data = self.env['hr.leave'].read_group(
             [('employee_id', 'in', employee_ids),
              # Använd holiday_status_id istället för is_swedish_sick_leave för databasfrågan
              ('holiday_status_id', '=', sick_leave_type.id),
              ('state', 'in', ['validate', 'validate1']),
              ('date_from', '>=', date_12_months_ago)
             ],
             ['employee_id', 'number_of_days:sum', 'count'], ['employee_id'])

        leave_map = {
             data['employee_id'][0]: {
                 'count': data['employee_id_count'], # read_group ger _count
                 'days': data['number_of_days']
                 } for data in leave_data
             }

        for employee in self:
             stats = leave_map.get(employee.id, {'count': 0, 'days': 0.0})
             employee.sick_leave_counter = stats['count']
             employee.sick_leave_days = stats['days']
             employee.frequently_ill = employee.sick_leave_counter > 6

    # --- Fält och metoder från hr_parental_leave_inherit.py ---
    parental_leave_days_used = fields.Float(
        string='Parental Leave Days Used (Total)', # Tydligare namn?
        compute='_compute_parental_leave_statistics'
    )
    # Behövs remaining? Det är per barn och komplext att beräkna totalt.
    # parental_leave_days_remaining = fields.Float(
    #     string='Parental Leave Days Remaining',
    #     compute='_compute_parental_leave_statistics'
    # )
    vab_days_used = fields.Float(
        string='VAB Days Used (This Year)',
        compute='_compute_parental_leave_statistics'
    )
    children_ids = fields.One2many(
        'hr.employee.child',
        'employee_id',
        string='Children'
    )

    def _compute_parental_leave_statistics(self):
        # Denna beräkning behöver göras mer effektivt
        parental_leave_type = self.env.ref('l10n_se_hr.holiday_status_swedish_parental_leave', raise_if_not_found=False)
        if not parental_leave_type:
             for employee in self:
                 # employee.parental_leave_days_used = 0.0
                 employee.vab_days_used = 0.0
             return # Kan inte beräkna utan typen

        employee_ids = self.ids
        if not employee_ids:
            return

        current_year_start = date(date.today().year, 1, 1)
        # current_year_end = date(date.today().year, 12, 31) # Behövs inte för VAB-queryn

        # Hämta all relevant data i en sökning om möjligt
        all_parental_leaves = self.env['hr.leave'].search([
            ('employee_id', 'in', employee_ids),
            ('holiday_status_id', '=', parental_leave_type.id), # Använd ID för sökning
            ('state', 'in', ['validate', 'validate1'])
        ])

        vab_map = {}
        # parental_days_map = {} # Totala dagar är svårt att beräkna generellt utan mer info

        for leave in all_parental_leaves:
             # VAB this year
             if leave.parental_leave_type == 'temporary' and leave.date_from.date() >= current_year_start:
                  vab_map[leave.employee_id.id] = vab_map.get(leave.employee_id.id, 0.0) + leave.number_of_days
             # Parental days total (simplifierat - räknar alla typer utom VAB?)
             # if leave.parental_leave_type != 'temporary':
             #      parental_days_map[leave.employee_id.id] = parental_days_map.get(leave.employee_id.id, 0.0) + leave.number_of_days

        for employee in self:
             # employee.parental_leave_days_used = parental_days_map.get(employee.id, 0.0)
             employee.vab_days_used = vab_map.get(employee.id, 0.0)
             # Beräkning av remaining är utelämnad då den är komplex (per barn etc.)