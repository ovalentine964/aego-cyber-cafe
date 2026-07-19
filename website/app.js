/**
 * Aego Cyber Cafe - Main JavaScript
 * Lightweight, no dependencies. Mobile-first.
 * Updated: 2026-07-19 — Tech stack validation fixes
 */

// ============================================
// Navigation Toggle
// ============================================
function toggleNav() {
  var nav = document.getElementById('mainNav');
  nav.classList.toggle('active');
}

// Close nav when clicking a link (mobile)
document.addEventListener('DOMContentLoaded', function() {
  var nav = document.getElementById('mainNav');
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
  var nav = document.getElementById('mainNav');
  var toggle = document.querySelector('.nav-toggle');
  if (nav && !nav.contains(e.target) && toggle && !toggle.contains(e.target)) {
    nav.classList.remove('active');
  }
});

// ============================================
// Inline Validation Helpers
// ============================================
function clearFieldError(fieldId) {
  var field = document.getElementById(fieldId);
  if (!field) return;
  field.classList.remove('error');
  var errorEl = field.parentNode.querySelector('.field-error');
  if (errorEl) {
    errorEl.classList.remove('show');
    errorEl.textContent = '';
  }
}

function showFieldError(fieldId, message) {
  var field = document.getElementById(fieldId);
  if (!field) return;
  field.classList.add('error');
  var errorEl = field.parentNode.querySelector('.field-error');
  if (!errorEl) {
    errorEl = document.createElement('div');
    errorEl.className = 'field-error';
    field.parentNode.appendChild(errorEl);
  }
  errorEl.textContent = message;
  errorEl.classList.add('show');
  field.focus();
}

// Clear errors on input
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.form-control').forEach(function(el) {
    el.addEventListener('input', function() {
      clearFieldError(this.id);
    });
    el.addEventListener('change', function() {
      clearFieldError(this.id);
    });
  });
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

// ============================================
// Upsell Suggestions
// ============================================
var upsellMap = {
  'cv-basic': [
    { value: 'add-cover-letter', label: 'Add Cover Letter — KSh 150 more', price: 150 },
    { value: 'add-linkedin', label: 'Add LinkedIn Profile — KSh 200 more', price: 200 }
  ],
  'cv-pro': [
    { value: 'add-cover-letter', label: 'Add Cover Letter — KSh 150 more', price: 150 },
    { value: 'add-linkedin', label: 'Add LinkedIn Profile — KSh 200 more', price: 200 }
  ],
  'cv-exec': [],
  'kra-nil': [
    { value: 'add-nhif', label: 'Add NHIF Registration — KSh 200 more', price: 200 }
  ],
  'kra-income': [
    { value: 'add-nhif', label: 'Add NHIF Registration — KSh 200 more', price: 200 }
  ],
  'kra-pin': [
    { value: 'add-nhif', label: 'Add NHIF Registration — KSh 200 more', price: 200 }
  ],
  'cover-letter': [
    { value: 'add-linkedin', label: 'Add LinkedIn Profile — KSh 200 more', price: 200 }
  ]
};

// ============================================
// Dynamic field templates per service
// ============================================
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

  // Hide price display and addons when category changes
  var priceDisplay = document.getElementById('priceDisplay');
  if (priceDisplay) priceDisplay.classList.remove('show');
  var addons = document.getElementById('addonsSection');
  if (addons) addons.classList.remove('show');

  updateDynamicFields();
}

function getServicePrice(serviceValue) {
  for (var cat in serviceData) {
    for (var i = 0; i < serviceData[cat].length; i++) {
      if (serviceData[cat][i].value === serviceValue) {
        return serviceData[cat][i].price;
      }
    }
  }
  return 0;
}

function getServiceLabel(serviceValue) {
  for (var cat in serviceData) {
    for (var i = 0; i < serviceData[cat].length; i++) {
      if (serviceData[cat][i].value === serviceValue) {
        return serviceData[cat][i].label;
      }
    }
  }
  return '';
}

function updatePriceDisplay() {
  var serviceValue = document.getElementById('serviceType').value;
  var priceDisplay = document.getElementById('priceDisplay');
  var priceAmount = document.getElementById('priceAmount');
  var addonsSection = document.getElementById('addonsSection');
  var addonsList = document.getElementById('addonsList');

  if (!priceDisplay || !priceAmount) return;

  if (serviceValue) {
    var price = getServicePrice(serviceValue);
    if (price > 0) {
      priceAmount.textContent = 'KSh ' + price.toLocaleString();
    } else {
      priceAmount.textContent = 'Contact us for pricing';
    }
    priceDisplay.classList.add('show');

    // Show upsell suggestions
    if (addonsSection && addonsList) {
      addonsList.innerHTML = '';
      var upsells = upsellMap[serviceValue];
      if (upsells && upsells.length > 0) {
        upsells.forEach(function(addon) {
          var label = document.createElement('label');
          label.className = 'addon-label';
          var cb = document.createElement('input');
          cb.type = 'checkbox';
          cb.name = 'addon';
          cb.value = addon.value;
          cb.setAttribute('data-price', addon.price);
          cb.addEventListener('change', updateTotalPrice);
          label.appendChild(cb);
          label.appendChild(document.createTextNode(' ' + addon.label));
          addonsList.appendChild(label);
        });
        addonsSection.classList.add('show');
      } else {
        addonsSection.classList.remove('show');
      }
    }
  } else {
    priceDisplay.classList.remove('show');
    if (addonsSection) addonsSection.classList.remove('show');
  }

  updateTotalPrice();
}

function updateTotalPrice() {
  var serviceValue = document.getElementById('serviceType').value;
  var priceAmount = document.getElementById('priceAmount');
  if (!serviceValue || !priceAmount) return;

  var basePrice = getServicePrice(serviceValue);
  var addonTotal = 0;

  var addonCheckboxes = document.querySelectorAll('#addonsList input[name="addon"]:checked');
  addonCheckboxes.forEach(function(cb) {
    addonTotal += parseInt(cb.getAttribute('data-price')) || 0;
  });

  if (basePrice > 0) {
    var total = basePrice + addonTotal;
    var text = 'KSh ' + total.toLocaleString();
    if (addonTotal > 0) {
      text += ' (KSh ' + basePrice.toLocaleString() + ' + KSh ' + addonTotal.toLocaleString() + ' add-ons)';
    }
    priceAmount.textContent = text;
  }
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
    serviceType.addEventListener('change', function() {
      updateDynamicFields();
      updatePriceDisplay();
    });
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
      showFieldError('serviceCategory', 'Please select a service category.');
      return false;
    }
    if (!service) {
      showFieldError('serviceType', 'Please select a specific service.');
      return false;
    }
    return true;
  }

  if (step === 2) {
    var name = document.getElementById('fullName').value.trim();
    var phone = document.getElementById('phone').value.trim();
    var whatsapp = document.getElementById('whatsapp').value.trim();
    var valid = true;

    // Clear previous errors
    clearFieldError('fullName');
    clearFieldError('phone');
    clearFieldError('whatsapp');

    if (!name) {
      showFieldError('fullName', 'Please enter your full name.');
      valid = false;
    }
    if (!phone) {
      showFieldError('phone', 'Please enter your phone number.');
      valid = false;
    }
    if (!whatsapp) {
      showFieldError('whatsapp', 'Please enter your WhatsApp number.');
      valid = false;
    }

    // Validate phone format (Kenyan numbers - broad match)
    if (phone) {
      var phoneClean = phone.replace(/\s/g, '');
      if (!/^(\+?254|0)\d{9}$/.test(phoneClean)) {
        showFieldError('phone', 'Please enter a valid Kenyan phone number (e.g. 0712345678 or +254712345678).');
        valid = false;
      }
    }

    return valid;
  }

  return true;
}

// ============================================
// Submit Order — WhatsApp Redirect
// ============================================
function submitOrder() {
  // Validate step 2 fields
  var name = document.getElementById('fullName').value.trim();
  var phone = document.getElementById('phone').value.trim();
  var whatsapp = document.getElementById('whatsapp').value.trim();

  clearFieldError('mpesaCode');
  clearFieldError('amountPaid');

  var mpesaCode = document.getElementById('mpesaCode').value.trim();
  var amountPaid = document.getElementById('amountPaid').value.trim();
  var valid = true;

  if (!mpesaCode) {
    showFieldError('mpesaCode', 'Please enter your M-Pesa transaction code.');
    valid = false;
  }
  if (!amountPaid) {
    showFieldError('amountPaid', 'Please enter the amount paid.');
    valid = false;
  }
  if (!name || !phone || !whatsapp) {
    showFieldError('mpesaCode', 'Please go back and fill in your details.');
    valid = false;
  }
  if (!valid) return;

  // Collect form data
  var serviceType = document.getElementById('serviceType');
  var serviceLabel = serviceType.options[serviceType.selectedIndex].text;
  var details = document.getElementById('serviceDetails').value;
  var location = document.getElementById('location').value;

  // Collect add-ons
  var addonText = '';
  var addonCheckboxes = document.querySelectorAll('#addonsList input[name="addon"]:checked');
  if (addonCheckboxes.length > 0) {
    var addons = [];
    addonCheckboxes.forEach(function(cb) {
      addons.push(cb.parentNode.textContent.trim());
    });
    addonText = '\nAdd-ons: ' + addons.join(', ');
  }

  // Build WhatsApp message
  var waMsg = '📋 NEW ORDER\n\n' +
    'Service: ' + serviceLabel + '\n' +
    'Name: ' + name + '\n' +
    'Phone: ' + phone + '\n' +
    'M-Pesa Code: ' + mpesaCode + '\n' +
    'Amount: KSh ' + amountPaid + addonText + '\n' +
    (details ? 'Details: ' + details + '\n' : '') +
    (location ? 'Location: ' + location + '\n' : '') +
    '\nSent from aegocybercafe.co.ke';

  // Show success message
  document.getElementById('step3').style.display = 'none';
  document.getElementById('successMessage').classList.add('show');

  // Auto-redirect to WhatsApp
  var waUrl = 'https://wa.me/254712345678?text=' + encodeURIComponent(waMsg);

  // Update the WhatsApp confirm link
  var waLink = document.querySelector('#successMessage .btn-green');
  if (waLink) {
    waLink.href = waUrl;
  }

  // Auto-open WhatsApp after short delay
  setTimeout(function() {
    window.open(waUrl, '_blank');
  }, 1500);

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
  var valid = true;

  clearFieldError('contactName');
  clearFieldError('contactPhone');
  clearFieldError('contactMessage');

  if (!name) {
    showFieldError('contactName', 'Please enter your name.');
    valid = false;
  }
  if (!phone) {
    showFieldError('contactPhone', 'Please enter your phone number.');
    valid = false;
  }
  if (!message) {
    showFieldError('contactMessage', 'Please enter your message.');
    valid = false;
  }
  if (!valid) return;

  // Send via WhatsApp
  var waMsg = '💬 CONTACT MESSAGE\n\n' +
    'Name: ' + name + '\n' +
    'Phone: ' + phone + '\n' +
    'Message: ' + message + '\n' +
    '\nSent from aegocybercafe.co.ke';

  var waUrl = 'https://wa.me/254712345678?text=' + encodeURIComponent(waMsg);

  // Show success
  document.getElementById('contactForm').style.display = 'none';
  document.getElementById('contactSuccess').classList.add('show');

  // Open WhatsApp
  window.open(waUrl, '_blank');
}

// ============================================
// Smooth Scroll for anchor links
// ============================================
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('a[href^="#"]').forEach(function(anchor) {
    anchor.addEventListener('click', function(e) {
      var href = this.getAttribute('href');
      if (href.length > 1) {
        var target = document.querySelector(href);
        if (target) {
          e.preventDefault();
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }
    });
  });
});
