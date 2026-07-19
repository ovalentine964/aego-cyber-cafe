/**
 * Aego Cyber Cafe - Main JavaScript
 * Lightweight, no dependencies. Mobile-first.
 */

// ============================================
// Navigation Toggle
// ============================================
function toggleNav() {
  const nav = document.getElementById('mainNav');
  nav.classList.toggle('active');
}

// Close nav when clicking a link (mobile)
document.addEventListener('DOMContentLoaded', function() {
  const nav = document.getElementById('mainNav');
  if (nav) {
    nav.querySelectorAll('a').forEach(function(link) {
      link.addEventListener('click', function() {
        nav.classList.remove('active');
      });
    });
  }
});

// Close nav when clicking outside
document.addEventListener('click', function(e) {
  const nav = document.getElementById('mainNav');
  const toggle = document.querySelector('.nav-toggle');
  if (nav && !nav.contains(e.target) && toggle && !toggle.contains(e.target)) {
    nav.classList.remove('active');
  }
});

// ============================================
// Service Data
// ============================================
var serviceData = {
  government: [
    { value: 'kra-pin', label: 'KRA PIN Registration — KSh 300', price: 300 },
    { value: 'kra-nil', label: 'KRA Nil Returns — KSh 200', price: 200 },
    { value: 'kra-income', label: 'KRA Income Returns — KSh 500', price: 500 },
    { value: 'kra-reprint', label: 'KRA PIN Certificate Reprint — KSh 200', price: 200 },
    { value: 'ecitizen-register', label: 'eCitizen Account Registration — KSh 300', price: 300 },
    { value: 'good-conduct', label: 'Certificate of Good Conduct — KSh 1,200', price: 1200 },
    { value: 'birth-cert', label: 'Birth Certificate — KSh 500', price: 500 },
    { value: 'death-cert', label: 'Death Certificate — KSh 500', price: 500 },
    { value: 'nhif-register', label: 'NHIF Registration — KSh 300', price: 300 },
    { value: 'nhif-update', label: 'NHIF Update — KSh 200', price: 200 },
    { value: 'nssf-register', label: 'NSSF Registration — KSh 300', price: 300 },
    { value: 'ntsa-license', label: 'Driving License — KSh 800', price: 800 },
    { value: 'ntsa-logbook', label: 'Logbook Transfer — KSh 1,500', price: 1500 },
    { value: 'helb-apply', label: 'HELB Application — KSh 500', price: 500 },
    { value: 'passport', label: 'Passport Application — KSh 1,000', price: 1000 },
    { value: 'other-gov', label: 'Other Government Service', price: 0 }
  ],
  cv: [
    { value: 'cv-basic', label: 'CV Writing (Basic) — KSh 300', price: 300 },
    { value: 'cv-pro', label: 'CV Writing (Professional) — KSh 500', price: 500 },
    { value: 'cv-exec', label: 'CV Writing (Executive) — KSh 1,000', price: 1000 },
    { value: 'cover-letter', label: 'Cover Letter — KSh 300', price: 300 },
    { value: 'app-letter', label: 'Application Letter — KSh 250', price: 250 },
    { value: 'business-plan', label: 'Business Plan (Basic) — KSh 2,000', price: 2000 },
    { value: 'business-plan-full', label: 'Business Plan (Detailed) — KSh 5,000', price: 5000 },
    { value: 'proposal', label: 'Proposal Writing — KSh 1,500', price: 1500 },
    { value: 'report', label: 'Report Writing — KSh 1,000', price: 1000 },
    { value: 'typing', label: 'Typing — KSh 100/page', price: 100 }
  ],
  printing: [
    { value: 'bw-print', label: 'B&W Printing — KSh 10/page', price: 10 },
    { value: 'color-print', label: 'Colour Printing — KSh 50/page', price: 50 },
    { value: 'photocopy', label: 'Photocopying — KSh 5/page', price: 5 },
    { value: 'scanning', label: 'Scanning — KSh 50/page', price: 50 },
    { value: 'lamination', label: 'Lamination — KSh 100', price: 100 },
    { value: 'binding', label: 'Binding — KSh 150', price: 150 }
  ],
  design: [
    { value: 'flyer', label: 'Flyer/Poster Design — From KSh 500', price: 500 },
    { value: 'biz-card', label: 'Business Cards — From KSh 800', price: 800 },
    { value: 'social-media', label: 'Social Media Graphics — From KSh 300', price: 300 },
    { value: 'logo', label: 'Logo Design — From KSh 1,500', price: 1500 }
  ],
  student: [
    { value: 'school-app', label: 'School Application — KSh 300', price: 300 },
    { value: 'scholarship', label: 'Scholarship Essay — KSh 500', price: 500 },
    { value: 'research', label: 'Research Project — KSh 1,500', price: 1500 },
    { value: 'internet', label: 'Internet Access — KSh 1/min', price: 0 }
  ],
  business: [
    { value: 'biz-name', label: 'Business Name Registration — KSh 1,500', price: 1500 },
    { value: 'company-reg', label: 'Company Registration — KSh 5,000', price: 5000 },
    { value: 'biz-kra', label: 'Business KRA PIN — KSh 500', price: 500 },
    { value: 'tax-monthly', label: 'Monthly Tax Filing — KSh 500', price: 500 },
    { value: 'tax-annual', label: 'Annual Tax Filing — KSh 1,000', price: 1000 },
    { value: 'financial-analysis', label: 'Financial Analysis — KSh 1,500', price: 1500 },
    { value: 'bookkeeping', label: 'Monthly Bookkeeping — KSh 2,000', price: 2000 },
    { value: 'tender', label: 'Tender Application — KSh 1,000', price: 1000 }
  ],
  other: [
    { value: 'other', label: 'Other (describe in details below)', price: 0 }
  ]
};

// Dynamic field templates per service
var dynamicFieldTemplates = {
  'kra-pin': [
    { label: 'ID Number', id: 'idNumber', type: 'text', placeholder: 'Your national ID number', required: true },
    { label: 'Full Name (as on ID)', id: 'fullNameID', type: 'text', placeholder: 'Exactly as on your ID', required: true }
  ],
  'kra-nil': [
    { label: 'KRA PIN', id: 'kraPin', type: 'text', placeholder: 'e.g. A001234567B', required: true }
  ],
  'kra-income': [
    { label: 'KRA PIN', id: 'kraPin', type: 'text', placeholder: 'e.g. A001234567B', required: true },
    { label: 'Tax Year', id: 'taxYear', type: 'text', placeholder: 'e.g. 2025', required: true }
  ],
  'good-conduct': [
    { label: 'ID Number', id: 'idNumber', type: 'text', placeholder: 'Your national ID number', required: true },
    { label: 'eCitizen Password', id: 'ecitizenPass', type: 'password', placeholder: 'Your eCitizen account password', required: true }
  ],
  'passport': [
    { label: 'ID Number', id: 'idNumber', type: 'text', placeholder: 'Your national ID number', required: true },
    { label: 'Passport Type', id: 'passportType', type: 'select', options: ['New Passport', 'Renewal', 'Replacement'], required: true }
  ],
  'cv-basic': [
    { label: 'Target Job/Position', id: 'targetJob', type: 'text', placeholder: 'e.g. Accountant, Teacher, Sales Rep', required: true }
  ],
  'cv-pro': [
    { label: 'Target Job/Position', id: 'targetJob', type: 'text', placeholder: 'e.g. Accountant, Teacher, Sales Rep', required: true },
    { label: 'Years of Experience', id: 'experience', type: 'text', placeholder: 'e.g. 3 years', required: false }
  ],
  'cv-exec': [
    { label: 'Target Job/Position', id: 'targetJob', type: 'text', placeholder: 'e.g. Finance Manager, Operations Director', required: true },
    { label: 'Years of Experience', id: 'experience', type: 'text', placeholder: 'e.g. 10 years', required: true }
  ],
  'cover-letter': [
    { label: 'Job Title & Company', id: 'jobTitle', type: 'text', placeholder: 'e.g. Accountant at Safaricom', required: true }
  ],
  'business-plan': [
    { label: 'Business Name', id: 'bizName', type: 'text', placeholder: 'Your business name', required: true },
    { label: 'Business Type', id: 'bizType', type: 'text', placeholder: 'e.g. Restaurant, Retail Shop', required: true }
  ],
  'business-plan-full': [
    { label: 'Business Name', id: 'bizName', type: 'text', placeholder: 'Your business name', required: true },
    { label: 'Business Type', id: 'bizType', type: 'text', placeholder: 'e.g. Restaurant, Retail Shop', required: true },
    { label: 'Funding Purpose', id: 'fundingPurpose', type: 'text', placeholder: 'e.g. Bank loan, Grant application', required: false }
  ]
};

// ============================================
// Order Form Logic
// ============================================
function updateServices() {
  var category = document.getElementById('serviceCategory').value;
  var serviceSelect = document.getElementById('serviceType');
  serviceSelect.innerHTML = '<option value="">— Select a service —</option>';

  if (category && serviceData[category]) {
    serviceData[category].forEach(function(svc) {
      var opt = document.createElement('option');
      opt.value = svc.value;
      opt.textContent = svc.label;
      serviceSelect.appendChild(opt);
    });
  }

  // Update dynamic fields
  updateDynamicFields();
}

function updateDynamicFields() {
  var service = document.getElementById('serviceType').value;
  var container = document.getElementById('dynamicFields');
  if (!container) return;

  container.innerHTML = '';

  if (service && dynamicFieldTemplates[service]) {
    dynamicFieldTemplates[service].forEach(function(field) {
      var group = document.createElement('div');
      group.className = 'form-group';

      var label = document.createElement('label');
      label.setAttribute('for', field.id);
      label.textContent = field.label + (field.required ? ' *' : '');
      group.appendChild(label);

      if (field.type === 'select') {
        var select = document.createElement('select');
        select.className = 'form-control';
        select.id = field.id;
        if (field.required) select.required = true;
        select.innerHTML = '<option value="">— Select —</option>';
        if (field.options) {
          field.options.forEach(function(opt) {
            var option = document.createElement('option');
            option.value = opt;
            option.textContent = opt;
            select.appendChild(option);
          });
        }
        group.appendChild(select);
      } else {
        var input = document.createElement('input');
        input.type = field.type;
        input.className = 'form-control';
        input.id = field.id;
        input.placeholder = field.placeholder || '';
        if (field.required) input.required = true;
        group.appendChild(input);
      }

      container.appendChild(group);
    });
  }
}

// Listen for service type change
document.addEventListener('DOMContentLoaded', function() {
  var serviceType = document.getElementById('serviceType');
  if (serviceType) {
    serviceType.addEventListener('change', updateDynamicFields);
  }

  // Pre-select service from URL
  var params = new URLSearchParams(window.location.search);
  var preService = params.get('service');
  if (preService) {
    var catSelect = document.getElementById('serviceCategory');
    if (catSelect) {
      catSelect.value = preService;
      updateServices();
    }
  }
});

// ============================================
// Step Navigation
// ============================================
var currentStep = 1;

function goToStep(step) {
  // Validate current step before advancing
  if (step > currentStep) {
    if (!validateStep(currentStep)) return;
  }

  // Hide all steps
  for (var i = 1; i <= 3; i++) {
    var el = document.getElementById('step' + i);
    if (el) el.style.display = 'none';
    var indicator = document.getElementById('step' + i + 'indicator');
    if (indicator) indicator.classList.remove('active');
  }

  // Show target step
  var target = document.getElementById('step' + step);
  if (target) target.style.display = 'block';
  var targetIndicator = document.getElementById('step' + step + 'indicator');
  if (targetIndicator) targetIndicator.classList.add('active');

  currentStep = step;

  // Scroll to top of form
  window.scrollTo({ top: 200, behavior: 'smooth' });
}

function validateStep(step) {
  if (step === 1) {
    var category = document.getElementById('serviceCategory').value;
    var service = document.getElementById('serviceType').value;
    if (!category) {
      alert('Please select a service category.');
      return false;
    }
    if (!service) {
      alert('Please select a specific service.');
      return false;
    }
    return true;
  }

  if (step === 2) {
    var name = document.getElementById('fullName').value.trim();
    var phone = document.getElementById('phone').value.trim();
    var whatsapp = document.getElementById('whatsapp').value.trim();

    if (!name) { alert('Please enter your full name.'); return false; }
    if (!phone) { alert('Please enter your phone number.'); return false; }
    if (!whatsapp) { alert('Please enter your WhatsApp number.'); return false; }

    // Validate phone format (basic Kenyan)
    var phoneClean = phone.replace(/\s/g, '');
    if (!/^(\+?254|0)[17]\d{8}$/.test(phoneClean)) {
      alert('Please enter a valid Kenyan phone number (e.g. 0712345678 or +254712345678).');
      return false;
    }

    return true;
  }

  return true;
}

// ============================================
// Submit Order
// ============================================
function submitOrder() {
  if (!validateStep(2)) return;

  var mpesaCode = document.getElementById('mpesaCode').value.trim();
  var amountPaid = document.getElementById('amountPaid').value.trim();

  if (!mpesaCode) {
    alert('Please enter your M-Pesa transaction code.');
    return;
  }
  if (!amountPaid) {
    alert('Please enter the amount paid.');
    return;
  }

  // Collect all form data
  var orderData = {
    service: document.getElementById('serviceType').value,
    serviceLabel: document.getElementById('serviceType').options[document.getElementById('serviceType').selectedIndex].text,
    category: document.getElementById('serviceCategory').value,
    details: document.getElementById('serviceDetails').value,
    name: document.getElementById('fullName').value,
    phone: document.getElementById('phone').value,
    email: document.getElementById('email').value,
    whatsapp: document.getElementById('whatsapp').value,
    location: document.getElementById('location').value,
    mpesaCode: mpesaCode,
    amountPaid: amountPaid,
    timestamp: new Date().toISOString()
  };

  // Log order (in production, this would POST to a server)
  console.log('ORDER SUBMITTED:', orderData);

  // Show success message
  document.getElementById('step3').style.display = 'none';
  document.getElementById('successMessage').classList.add('show');

  // In production: send order data to server via fetch()
  // fetch('/api/orders', { method: 'POST', body: JSON.stringify(orderData) });

  // For now, construct a WhatsApp message with order details
  var waMsg = encodeURIComponent(
    '📋 NEW ORDER\n\n' +
    'Service: ' + orderData.serviceLabel + '\n' +
    'Name: ' + orderData.name + '\n' +
    'Phone: ' + orderData.phone + '\n' +
    'M-Pesa Code: ' + orderData.mpesaCode + '\n' +
    'Amount: KSh ' + orderData.amountPaid + '\n' +
    (orderData.details ? 'Details: ' + orderData.details + '\n' : '') +
    (orderData.location ? 'Location: ' + orderData.location + '\n' : '')
  );

  // Update the success WhatsApp link
  var waLink = document.querySelector('#successMessage .btn-green');
  if (waLink) {
    waLink.href = 'https://wa.me/254700000000?text=' + waMsg;
  }

  window.scrollTo({ top: 300, behavior: 'smooth' });
}

// ============================================
// Contact Form
// ============================================
function submitContact(e) {
  e.preventDefault();

  var name = document.getElementById('contactName').value.trim();
  var phone = document.getElementById('contactPhone').value.trim();
  var message = document.getElementById('contactMessage').value.trim();

  if (!name || !phone || !message) {
    alert('Please fill in all required fields.');
    return;
  }

  // Show success
  document.getElementById('contactForm').style.display = 'none';
  document.getElementById('contactSuccess').classList.add('show');

  // In production: send to server
  console.log('CONTACT FORM:', { name: name, phone: phone, message: message });
}

// ============================================
// Smooth Scroll for anchor links
// ============================================
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('a[href^="#"]').forEach(function(anchor) {
    anchor.addEventListener('click', function(e) {
      var target = document.querySelector(this.getAttribute('href'));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });
});
