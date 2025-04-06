# Group URLs Analysis

**Objective:** Analyze University of Idaho group/department pages to identify patterns and challenges in locating and extracting links to individual faculty/staff profiles and associated data displayed directly on the group page.

## Summary of Findings

*   **Primary Target:** Most profiles are found within `div.ui-obj-person-promo.row`.
*   **Mixed Content:** Pages often contain a mix of individuals with dedicated profile links and those without. Data extraction is required even when no link exists.
*   **Link Variations:** Profile links can appear in multiple places (name `<h2>`, separate "View Profile" link). External links (e.g., scheduling) also exist. Deduplication and handling of non-standard links are necessary.
*   **Data Variability:** The presence and structure of specific data points (image, contact info) vary significantly. Robust handling of missing data is crucial.
*   **Structural Outliers:** Some pages (e.g., OIT) deviate significantly from the common structure, requiring specific handling or potentially separate logic.

## Analyzed URLs and Key Observations
*   **URL:** `https://www.uidaho.edu/engr/our-people/deans-office`
    *   **Observation:** Contains a mix of individuals with and without dedicated profile page links. Data for all individuals is present within `div.ui-obj-person-promo.row`. Requires extracting both available profile links *and* data directly from this page.
*   **URL:** `https://www.uidaho.edu/engr/our-people/student-services`
    *   **Observation:** Similar structure (`div.ui-obj-person-promo.row`, `div.info-container`). Content varies; includes advisors with external scheduling links (`outlook.office365.com`). Some profiles have multiple links pointing to the same profile page (e.g., name link, "View Full Profile" link). Link deduplication is necessary.
*   **URL:** `https://www.uidaho.edu/oit/about/people`
    *   **Observation:** Different structure. Profile data appears embedded directly on this page, not on separate profile pages. Contains a distinct "Leadership Team" section duplicating profiles listed above. Extraction logic must handle this structure and potential duplication.
*   **URL:** `https://www.uidaho.edu/class/politics-and-philosophy/our-people`
    *   **Observation:** Follows the pattern of the first two URLs (`div.ui-obj-person-promo.row`). All individuals appear to have profile links. Larger number of profiles (~20).
*   **URL:** `https://www.uidaho.edu/cogs/shamp/faculty-staff-directory`
    *   **Observation:** Similar pattern. Mix of individuals with and without profile links.
*   **URL:** `https://www.uidaho.edu/class/jamm/faculty-staff`
    *   **Observation:** Similar pattern. Includes distinct categories like "Emeritus" and "Affiliate" faculty. The scraper might need to handle or categorize these.

## Common HTML Structure & Patterns
*   **Primary Container:** Most individual profiles are encapsulated within a `div` having the classes `ui-obj-person-promo row`. This is the primary target element for identifying potential profiles.
*   **Profile Link:** When a dedicated profile page exists, the link is typically found within an `<a>` tag directly containing the person's name (often within an `<h2>` tag).
    *   **Variation:** Some profiles contain an additional explicit "View [...] Profile" link within `div.summary-container.top-line`, pointing to the same URL.
    *   **Variation:** Some profiles (e.g., advisors) link to external scheduling systems instead of a standard profile page.
*   **Image:** Profile pictures are usually within an `<img>` tag with class `img-responsive`. Alt text often contains the person's name. Image presence is not guaranteed.
*   **Contact/Details:** Contact information (location, phone, email) and other details (degrees, etc.) are often found within a `div` with the class `info-container`. Content and availability vary.

## Implications for Extraction Logic
1.  **Target Element:** The primary scraping logic should target `div.ui-obj-person-promo.row` elements.
2.  **Link Extraction:**
    *   Prioritize extracting the `href` from the `<a>` tag containing the `<h2>` (name).
    *   Check for the secondary "View Profile" link within `.summary-container.top-line > p > a` and deduplicate URLs.
    *   Identify and potentially flag or handle external links (e.g., `outlook.office365.com`) differently if they are not considered standard profiles.
3.  **Data Extraction:** Extract Name, Title, Image URL, and details from within the `div.ui-obj-person-promo.row`, even if a profile link is not present. The presence of each data point (image, email, phone, etc.) is variable and needs robust handling (e.g., returning `None` if not found).
4.  **Handling Variations:** The scraper must be resilient to missing elements (images, contact info, profile links) and structural differences (like the OIT page).
5.  **Deduplication:** Implement logic to avoid adding the same profile URL multiple times if encountered via different links on the same page.

## HTML Examples

*(Keep existing HTML examples as they are valuable)*

#### Example 1: Profile with Redundant Link

```html





	<div class="col-sm-12 col-md-6 col-lg-4">

		

		<!-- DynamicPlaceholder( "column-one" ) -->
		








 


 



<!-- Components\PersonPromo.cshtml -->
<div class="ui-obj-person-promo row">
  <div class="col-sm-12">
      
          <a href="/cogs/shamp/wwami/our-people/faculty/jeff-seegmiller">
              <h2>Jeff Seegmiller, Ed.D., LAT, ATC</h2>
          </a>

      
      <h3>Regional Dean and Director</h3>
  </div>
  <div class="col-sm-12">
      
          <a href="/cogs/shamp/wwami/our-people/faculty/jeff-seegmiller">
              <img src="/-/media/uidaho-responsive/images/cogs/shamp/wwami/fac-staff/jeff-seegmiller.jpg?h=660&amp;la=en&amp;w=660&amp;rev=27a2f894aeab4d398508e4d751fcfd99" class="img-responsive" alt="Jeff Seegmiller" width="660" height="660">
          </a>
  </div>
  <div class="col-sm-12">
    <div class="info-container">
        <!-- PersonDetails() -->
          <p>WWAMI Medical Education Building</p>
          <p>208-885-6696</p>
          <p><a href="mailto:jeffreys@uidaho.edu">jeffreys@uidaho.edu</a></p>
    <div class="summary-container top-line">
        <p><a href="/cogs/shamp/wwami/our-people/faculty/jeff-seegmiller">View Jeff Seegmiller's profile</a></p>
    </div>

    </div>
  </div>

</div>

</div>
<div class="col-sm-12 col-md-6 col-lg-4">
  <!-- DynamicPlaceholder( "column-two" ) -->
  
</div>
<div class="col-sm-12 col-md-12 col-lg-4">
  <!-- DynamicPlaceholder( "column-three" ) -->
  
</div>
```

#### Example 2: Profile with Scheduling Link (No Standard Profile Link)

```html
<div class="ui-obj-person-promo row">
		<div class="col-sm-12">
				
						<a href="https://outlook.office365.com/owa/calendar/AdvisingAppointmentswithBrianCox@vandalsuidaho.onmicrosoft.com/bookings/">
								<h2>Brian Cox</h2>
						</a>

				
				<h3>Academic Advisor</h3>
		</div>
		<div class="col-sm-12">
				
						<a href="https://outlook.office365.com/owa/calendar/AdvisingAppointmentswithBrianCox@vandalsuidaho.onmicrosoft.com/bookings/">
								<img src="/-/media/uidaho-responsive/images/current-students/academic-advising/advisor-headshots/brian-cox.jpg?h=1200&amp;la=en&amp;w=1200&amp;rev=3a626753a719455f9280c0a0efd9c97b" class="img-responsive" alt="Brian Cox" width="1200" height="1200">
						</a>
		</div>
		<div class="col-sm-12">
			<div class="info-container">
				 <!-- PersonDetails() -->
            <p>JEB 125B</p>
            <p>208-885-0125</p>
            <p><a href="mailto:briantc@uidaho.edu">briantc@uidaho.edu</a></p>
			<div class="summary-container top-line">
					<p><a href="https://outlook.office365.com/owa/calendar/AdvisingAppointmentswithBrianCox@vandalsuidaho.onmicrosoft.com/bookings/">Schedule with Brian</a></p>
			</div>
 
			</div>
		</div>
  
</div>
```