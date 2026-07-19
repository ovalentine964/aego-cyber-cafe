# Aego Cyber Cafe Website

AI-powered digital services in Nyatike, Migori County, Kenya.

## 🚀 Quick Deploy — GitHub Pages (Free Hosting)

### Step 1: Create a GitHub Repository
1. Go to [github.com](https://github.com) and sign in (or create an account)
2. Click **New Repository**
3. Name it: `aego-cyber-cafe` (or any name you like)
4. Make it **Public**
5. Click **Create Repository**

### Step 2: Upload Your Files
1. Click **"uploading an existing file"** on the repo page
2. Upload ALL files from this `website/` folder:
   - `index.html` (homepage)
   - `services.html`
   - `order.html`
   - `about.html`
   - `diaspora.html`
   - `blog.html`
   - `contact.html`
   - `style.css`
   - `app.js`
   - `robots.txt`
   - `sitemap.xml`
3. Click **Commit changes**

### Step 3: Enable GitHub Pages
1. Go to your repo → **Settings** → **Pages**
2. Under **Source**, select: `main` branch, `/ (root)` folder
3. Click **Save**
4. Wait 2–3 minutes
5. Your site is live at: `https://yourusername.github.io/aego-cyber-cafe/`

### Step 4: Custom Domain (Optional)
If you own a domain like `aegocybercafe.co.ke`:
1. In GitHub Pages settings, add your custom domain
2. Add a `CNAME` file with your domain
3. Update your domain's DNS:
   - Add `A` records pointing to GitHub's IPs:
     - `185.199.108.153`
     - `185.199.109.153`
     - `185.199.110.153`
     - `185.199.111.153`
   - Or add a `CNAME` record pointing to `yourusername.github.io`
4. Enable **Enforce HTTPS** in GitHub Pages settings

## 💬 WhatsApp Business Setup

1. Download **WhatsApp Business** from Google Play / App Store
2. Register with your business phone number
3. Set up your business profile:
   - Business name: **Aego Cyber Cafe**
   - Category: **Professional Services**
   - Description: AI-powered digital services in Nyatike, Migori County
   - Address: Nyatike Town, Migori County
   - Business hours: Mon–Sat 8AM–6PM, Sun 9AM–1PM
4. Update the WhatsApp number in all HTML files (search for `254700000000` and replace with your actual number)

## 📱 M-Pesa Paybill

The website uses Paybill: **0115 965 493** (already configured for Valentine's account).

To update:
1. Search all HTML files for `0115 965 493`
2. Replace with your actual Paybill number

## 🎨 Customization

### Update Phone Numbers
Search all `.html` files for:
- `254700000000` → Replace with your WhatsApp/phone number
- `+254 700 000 000` → Replace with your display number
- `0700 000 000` → Replace with your display number

### Update Location
In `contact.html`, update the Google Maps embed URL with your exact location coordinates.

### Update Prices
In `services.html`, edit the price tables to match your current pricing.

### Add Blog Posts
In `blog.html`, copy an existing blog post section and update the content. Each blog post targets SEO keywords that people in Migori County search for.

## 📊 SEO Tips

1. **Google My Business**: Create a listing for "Aego Cyber Cafe, Nyatike"
2. **Google Search Console**: Submit your sitemap at [search.google.com/search-console](https://search.google.com/search-console)
3. **Keywords to target**:
   - "cyber cafe Nyatike"
   - "KRA services Migori"
   - "CV writing Kenya"
   - "eCitizen services Migori County"
   - "printing services Nyatike"
   - "Kenyan diaspora services"

## 📁 File Structure

```
website/
├── index.html          # Homepage
├── services.html       # Full services & prices
├── order.html          # Online service ordering
├── about.html          # About Valentine & the cafe
├── diaspora.html       # Diaspora services (Kenyans abroad)
├── blog.html           # Tips & guides (SEO content)
├── contact.html        # Contact page
├── style.css           # All styles (mobile-first)
├── app.js              # JavaScript (form logic, nav, WhatsApp)
├── robots.txt          # Search engine instructions
├── sitemap.xml         # Sitemap for Google
└── README.md           # This file
```

## ⚡ Performance

- Total CSS: ~17KB
- Total JS: ~16KB
- No external frameworks or libraries
- No heavy images (uses emoji icons)
- Mobile-first design
- Optimized for slow rural internet

## 🔧 Technical Notes

- **No build step required** — just upload HTML/CSS/JS files
- **No server needed** — works on GitHub Pages, Netlify, or any static host
- **No database** — order form logs to console (integrate with a backend later)
- **WhatsApp deep links** — opens WhatsApp with pre-filled messages
- **M-Pesa integration** — shows paybill instructions (STK push requires Safaricom API)

## 📞 Support

For website updates or technical help, contact the developer.

---

Built with ❤️ for Aego Cyber Cafe, Nyatike, Migori County.
