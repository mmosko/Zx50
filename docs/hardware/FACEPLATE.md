# Zx50 Enclosure & Faceplate Fabrication Guide

## 1. The KiCad to VCarve Pipeline
To guarantee your physical faceplate perfectly matches your PCB, the design must originate in KiCad.

* **Prep the KiCad Canvas:** Switch to the `User.Drawings` layer. Draw exact rectangles over your HCMS and LCD displays. Draw 3mm circles over every single LED. Add your UI text labels. 
* **Add Alignment Dowel Holes:** Place four 1/4" (or 6mm) circles outside the main 7x7" faceplate boundary. These will be your alignment dowel holes for the CNC "flip jig."
* **Export the DXF:** Go to `File -> Export -> DXF`. Select *only* the `Edge.Cuts` and `User.Drawings` layers. Check the box for **"Use drill/place file origin"**.
* **Import to VCarve:** Import the DXF. Double-check the dimensions to ensure it imported at exactly 100% scale (no metric/imperial conversion scaling errors).
* **Set Up the Two-Sided Job:** Use VCarve’s two-sided machining setup. Center the job on your dowel hole vectors so the front and back toolpaths are mathematically locked together.



## 2. Faceplate Fabrication (Smoked Acrylic)
*Material: 7" x 7" Smoked Cast Acrylic (1/8" or 1/4" thick)*

### Front-Side Machining (The Stealth UI)
* **Masking:** Apply standard blue painter's tape or paper transfer tape across the entire top surface.
* **Alignment Holes:** Mill the 4 outer dowel holes completely through the stock and into your CNC spoilboard. 
* **V-Carving:** Use a 60° or 90° V-bit to engrave your UI text (`RUN`, `STEP`, `POWER`, etc.) right through the tape, about 0.5mm to 1.0mm deep.
* **Paint Fill:** Before removing the tape, smear white acrylic paint or enamel into the engraved text. Scrape the excess off with a plastic card. Let it dry, then peel the tape.

### Rear-Side Machining (The Pockets & Mounting)
* **The Flip:** Remove the acrylic, tap your wooden dowels into the spoilboard, flip the acrylic left-to-right, and press it onto the dowels.
* **Display Windows:** Use a flat-bottom end mill to cut the rectangular pockets for the HCMS and LCD displays. **Cut 1.0mm deep** into the rear. *Leave the bottom frosted—it acts as a perfect light diffuser!*
* **LED Locking Pockets:** Use a 3.0mm end mill (or standard 1/8" bit) to plunge a 1.0mm deep pocket for each of your THT LEDs. 
* **Through-Holes:** Drill the 6.5mm (1/4") holes for the four NKK switches, and the 3.2mm (1/8") holes for the left-side M3 standoffs.
* **Perimeter Cut:** Run the final profile cutout to free the 7x7" faceplate from the stock.

## 3. Chassis Fabrication (Clear Acrylic)
*Material: Clear Cast Acrylic*

### Bottom Plate (The Foundation)
* **Cut Outline:** Mill the bottom plate to accommodate your 6.75" internal width requirement (final width depends on your chosen wall thickness). Target a minimum internal depth of 10.0".
* **Backplane Mounting:** Mill the M3 standoff mounting holes for the 8.5" x 6.5" backplane. Ensure the front edge of the backplane is offset at least 1.5" from the faceplate to allow the IDC ribbon cable to make its "U-turn."

### Side & Rear Plates
* **Interlocking:** If using the CNC, design box joints or tab-and-slot geometry in VCarve to make the clear acrylic box self-squaring.
* **Rear I/O:** Mill the cutout for your Mean Well power entry connector and any external serial/expansion ports. 
* **Top Clearance:** Verify the side walls are tall enough that a 5" tall CPU card sitting in the backplane slot clears the roof of the enclosure (target ~6.0" internal height).

## 4. CNC Pro-Tips for Acrylic
1.  **Use an O-Flute Bit:** Standard wood end-mills will melt acrylic, wrapping molten plastic around the bit until it snaps. Use a **Single-Flute O-Flute upcut bit**. 
2.  **Cast vs. Extruded:** Always buy *Cast* acrylic for CNC routing. Extruded acrylic has a lower melting point and cuts terribly. 
3.  **Feeds and Speeds:** Acrylic needs a high chip load to carry heat away from the cut. Keep your spindle RPM relatively low (10k-14k) and your feed rate fast (60-100 inches per minute) to ensure you are making chips, not dust or melted slag.

***
