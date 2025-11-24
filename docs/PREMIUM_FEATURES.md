# Premium vs Free Features

## Current Feature Comparison

### 🆓 Free Tier
**Apartment Limit:** 2 apartments maximum

**Included Features:**
- ✅ Compare up to 2 apartments side-by-side
- ✅ Calculate net effective rent with rent concession calculator
- ✅ Compare by multiple fields:
  - Monthly rent
  - Net effective rent
  - Square footage
  - Price per square foot
  - Lease term
  - Discounts (months free, weeks free, flat discount)
- ✅ Sortable columns (all fields)
- ✅ Mobile-responsive design with card view
- ✅ Mobile sorting dropdown
- ✅ Dark mode support
- ✅ Anonymous session storage (no account required)
- ✅ Guest access to try the tool

**Limitations:**
- ❌ Maximum 2 apartments only
- ❌ Data not saved long-term (session storage only)
- ❌ Cannot access data across devices

---

### 💎 Premium Tier
**Price:** $9.99/month or $99.99/year (save ~17%)

**All Free Features PLUS:**

#### Core Benefits
- ✅ **Unlimited apartments** - Compare as many properties as you need
- ✅ **Data persistence** - Apartments saved to cloud (Firestore)
- ✅ **Cross-device sync** - Access your comparisons anywhere
- ✅ **Account management** - Secure Google OAuth login
- ✅ **Premium badge** - Display in UI

#### Current Premium-Only Features
- ✅ Unlimited apartment comparisons (vs 2 limit)
- ✅ Cloud storage and sync
- ✅ Long-term data persistence
- ✅ Manage subscription via Stripe Customer Portal

---

## Planned Premium Features (Future)

### 📸 Media Uploads
**Status:** Planned

Add photos and videos to each apartment listing:
- Upload multiple photos per apartment (gallery view)
- Upload video tours
- Compare apartments visually side-by-side
- Cloud storage for media files (Google Cloud Storage / Firebase Storage)

**Implementation Notes:**
- File size limits (e.g., 10MB per photo, 100MB per video)
- Supported formats: JPG, PNG, WebP for photos; MP4, WebM for videos
- Thumbnail generation for videos
- Gallery carousel/lightbox view
- Mobile photo upload from camera

---

### 🗺️ Location & Maps
**Status:** Consideration

- Google Maps integration showing apartment locations
- Commute time calculator to work/school
- Nearby amenities (restaurants, grocery stores, transit)
- Neighborhood data (walkability score, crime stats)

---

### 📊 Advanced Analytics
**Status:** Consideration

- Historical price tracking
- Market comparison data
- Rent trends in the area
- Cost breakdown visualizations (charts/graphs)
- Export comparisons to PDF or Excel

---

### 🤝 Collaboration
**Status:** Consideration

- Share comparisons with roommates/family
- Real-time collaboration on apartment lists
- Comments and notes per apartment
- Voting/rating system for group decisions

---

### 📝 Custom Fields
**Status:** Consideration

- Add custom fields beyond default options
- Pet policy tracking
- Parking availability
- Utilities included
- Custom notes per apartment
- Tags and categories

---

### 🔔 Notifications & Alerts
**Status:** Consideration

- Price change alerts
- New listing notifications
- Lease expiration reminders
- Email/SMS notifications

---

### 📱 Mobile App
**Status:** Far Future

- Native iOS/Android apps
- Offline access
- Push notifications
- Camera integration for quick photo uploads

---

## Migration Path

### Anonymous → Free Account
When anonymous users sign up:
- Session data automatically migrated to cloud
- Maintains 2-apartment limit
- Can upgrade to Premium anytime

### Free → Premium
When free users upgrade:
- Instant unlock of unlimited apartments
- All existing data preserved
- Premium badge displayed
- Access to new features as they roll out

### Premium → Free (Downgrade)
If premium user cancels:
- Keep apartments but capped at 2 (oldest deleted)
- Lose access to premium-only features (photos, etc.)
- Data preserved for 90 days
- Can re-upgrade anytime to restore full access

---

## Technical Implementation Notes

### Current Stack
- **Backend:** Django (Python)
- **Database:** Firestore (NoSQL, cloud-native)
- **Authentication:** Google OAuth via Python Social Auth
- **Payments:** Stripe (monthly/annual subscriptions)
- **Deployment:** Google App Engine
- **Frontend:** Django templates + Vanilla JS + Tailwind CSS

### Premium Feature Requirements
For media uploads:
- Firebase Storage or Google Cloud Storage
- Image/video processing pipeline
- CDN for media delivery
- Storage quotas per user (e.g., 1GB per premium user)

---

## Pricing Strategy

### Current Pricing
- **Monthly:** $9.99/month
- **Annual:** $99.99/year (~$8.33/month, 17% savings)

### Future Considerations
- Educational discounts (students)
- Team/family plans (multiple users, shared comparisons)
- Enterprise tier (property managers, real estate agents)

---

## Feature Rollout Plan

**Phase 1 (Current):**
- ✅ Basic comparison tool
- ✅ Rent concession calculator
- ✅ 2-apartment free tier
- ✅ Unlimited premium tier
- ✅ Stripe subscriptions

**Phase 2 (Next):**
- 📸 Photo/video uploads
- 🗺️ Location/maps integration
- 📊 Basic analytics dashboard

**Phase 3 (Later):**
- 🤝 Collaboration features
- 📝 Custom fields
- 🔔 Notifications

**Phase 4 (Future):**
- 📱 Mobile apps
- 🏢 Enterprise features
