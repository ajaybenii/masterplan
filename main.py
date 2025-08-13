import streamlit as st
import os
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from google import genai
from google.genai import types
import pathlib
from dotenv import load_dotenv
import tempfile

# Load environment variables
load_dotenv()

# Your original create_plan_pdf function (unchanged)
def create_plan_pdf(image_path: str, output_pdf_path: str, page_size=A4) -> bool:
    try:
        original_image = Image.open(image_path)
    except FileNotFoundError:
        print(f"Error: Input image file not found at {image_path}")
        return False
    except Exception as e:
        print(f"Error opening image '{image_path}': {e}")
        return False

    if original_image.mode != 'RGB':
        original_image = original_image.convert('RGB')

    img_width, img_height = original_image.size
    quad_width = img_width // 2
    quad_height = img_height // 2

    quadrants = {
        "upper_left": (0, 0, quad_width, quad_height),
        "upper_right": (quad_width, 0, img_width, quad_height),
        "lower_left": (0, quad_height, quad_width, img_height),
        "lower_right": (quad_width, quad_height, img_width, img_height)
    }

    c = canvas.Canvas(output_pdf_path, pagesize=page_size)
    pdf_width, pdf_height = page_size

    # Page 1: Full Image
    aspect_ratio = img_width / img_height
    page_aspect_ratio = pdf_width / pdf_height
    if aspect_ratio > page_aspect_ratio:
        draw_width = pdf_width
        draw_height = pdf_width / aspect_ratio
    else:
        draw_height = pdf_height
        draw_width = pdf_height * aspect_ratio

    x_offset = (pdf_width - draw_width) / 2
    y_offset = (pdf_height - draw_height) / 2

    c.drawImage(ImageReader(original_image), x_offset, y_offset, width=draw_width, height=draw_height)
    c.drawString(40, 40, "Page 1: Full Plan Overview")
    c.showPage()

    # Pages 2-5: Quadrants
    quadrant_order = ["upper_left", "upper_right", "lower_left", "lower_right"]
    quadrant_labels = {
        "upper_left": "Page 2: Upper-Left Quadrant Detail",
        "upper_right": "Page 3: Upper-Right Quadrant Detail",
        "lower_left": "Page 4: Lower-Left Quadrant Detail",
        "lower_right": "Page 5: Lower-Right Quadrant Detail"
    }

    for quad_key in quadrant_order:
        cropped_quad = original_image.crop(quadrants[quad_key])
        quad_aspect_ratio = cropped_quad.width / cropped_quad.height
        if quad_aspect_ratio > page_aspect_ratio:
            draw_width_quad = pdf_width
            draw_height_quad = pdf_width / quad_aspect_ratio
        else:
            draw_height_quad = pdf_height
            draw_width_quad = pdf_height * quad_aspect_ratio

        x_offset_quad = (pdf_width - draw_width_quad) / 2
        y_offset_quad = (pdf_height - draw_height_quad) / 2

        c.drawImage(ImageReader(cropped_quad), x_offset_quad, y_offset_quad,
                    width=draw_width_quad, height=draw_height_quad)
        c.drawString(40, 40, quadrant_labels[quad_key])
        c.showPage()

    c.save()
    st.success(f"PDF '{output_pdf_path}' created successfully!")
    return True

# Modified get_plan_analysis function to accept a custom prompt
def get_plan_analysis(gemini_api_key: str, pdf_path: str, prompt_text: str) -> str:
    if not gemini_api_key:
        return "Error: Gemini API key not provided."
    if not os.path.exists(pdf_path):
        return f"Error: PDF file not found at {pdf_path}"
    if not prompt_text.strip():
        return "Error: Prompt text cannot be empty."

    # Initialize client with API key
    client = genai.Client(api_key=gemini_api_key)

    filepath = pathlib.Path(pdf_path)
    pdf_bytes = filepath.read_bytes()

    contents = [
        types.Part.from_bytes(
            data=pdf_bytes,
            mime_type='application/pdf',
        ),
        types.Part(text=prompt_text)
    ]

    with st.spinner("Analyzing plan with Gemini..."):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT"]
                ),
            )
            return response.text
        except Exception as e:
            return f"Error interacting with Gemini API: {e}. Check API key and model access."

# Streamlit app
def main():
    st.title("Plan PDF Generator and Analyzer")
    st.write("Upload a master plan or floor plan image to generate a PDF and get an analysis using Gemini API.")

    # Gemini API key input
    gemini_api_key = os.getenv("UAT_GEMINI_API_KEY")
    if not gemini_api_key:
        gemini_api_key = st.text_input("Enter your Gemini API Key", type="password")
        if not gemini_api_key:
            st.warning("Please provide a valid Gemini API key to proceed.")
            return

    # Plan type selection
    plan_type = st.radio("Select Plan Type", ("Master Plan", "Floor Plan"))
    is_master_plan = plan_type == "Master Plan"

    # Default prompts
    master_plan_llm_prompt_text = """
As the builder of this property, your task is to sell this master plan. Extract and present information from the provided PDF. Be concise, direct, and factual, adhering strictly to what is visibly presented or explicitly stated in the master plan sections, without assumptions or excessive synonyms. Utilize the detailed views from pages 2-5.

PDF Structure Overview:
Page 1: Full master plan view.
Page 2: Focus on the upper-left quadrant.
Page 3: Focus on the upper-right quadrant.
Page 4: Focus on the lower-left quadrant.
Page 5: Focus on the lower-right quadrant.

Present the master plan's features by describing the following points. Focus on rigorous, eye-catching details.
Project Scope: State the total land area, number of units, and number of towers. Mention project launch and completion dates if visible.
Land Use & Density: Identify and specify designated zones (e.g., residential, commercial, open spaces) and their visible allocations or percentages. State units per acre.
Connectivity & Access: Detail visible internal road networks, primary access points, and any significant external connectivity features. Mention widths if indicated.
On-Site Features & Amenities: List all explicitly drawn or labeled amenities (e.g., clubhouse, parks, sports courts, specific utility placements). State any visible area sizes for these features.
Key Dimensions & Figures: Provide any other directly stated measurements, capacities, or distinguishing numerical facts about the master plan components.
    """

    floor_plan_llm_prompt_text = """
As the builder of this property, your task is to sell this floor plan. Extract and present information from the provided PDF. Be concise, direct, and factual, adhering strictly to what is visibly presented or explicitly stated in the floor plan, without assumptions or excessive synonyms. Utilize the detailed views from pages 2-5 for granular insights into each section.

PDF Structure Overview:
Page 1: Full floor plan view.
Page 2: Focus on the upper-left quadrant.
Page 3: Focus on the upper-right quadrant.
Page 4: Focus on the lower-left quadrant.
Page 5: Focus on the lower-right quadrant.

Present the floor plan's features by describing the following points. Focus on rigorous, eye-catching details.
Unit Overview: State the visible unit typology (e.g., 2BHK, 3BHK). Provide overall visible area figures like Saleable Area and RERA Carpet Area, along with efficiency percentages if shown.
Room-by-Room Details: Identify and describe each primary room (e.g., Living, Dining, Kitchen, Master Bedroom, other Bedrooms, Bathrooms). State any visible dimensions (length x width) or explicit area measurements for each.
Functional Spaces & Flow: Detail visible utility areas, balconies (including number and area percentage if available), and storage niches. Describe the visible internal circulation and connectivity between spaces.
Key Dimensions & Features: Provide any other directly stated measurements such as floor-to-ceiling height. Mention visible design elements like the number of lifts per tower or units per floor if relevant to the unit's context.
Light & Ventilation Assessment: Based on the visible layout, describe the apparent natural light and ventilation characteristics of key areas, noting window placements or air flow indicators.
    """

    # Select default prompt based on plan type
    default_prompt_text = master_plan_llm_prompt_text if is_master_plan else floor_plan_llm_prompt_text

    # Prompt editing UI
    st.subheader("Edit Analysis Prompt")
    st.write("Modify the prompt below to customize the analysis. Leave as is to use the default prompt.")
    custom_prompt = st.text_area("Analysis Prompt", value=default_prompt_text, height=300)

    # Image upload
    uploaded_file = st.file_uploader("Upload Plan Image (JPG/PNG)", type=["jpg", "png", "jpeg"])

    if uploaded_file is not None:
        # Display uploaded image
        st.image(uploaded_file, caption="Uploaded Plan Image", use_column_width=True)

        # Create temporary files for image and PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_image:
            tmp_image.write(uploaded_file.read())
            image_path = tmp_image.name

        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_pdf:
            output_pdf_path = tmp_pdf.name

        if st.button("Generate PDF and Analyze"):
            # Step 1: Generate PDF
            pdf_created = create_plan_pdf(image_path, output_pdf_path, A4)

            if pdf_created:
                # Provide download link for the PDF
                with open(output_pdf_path, "rb") as pdf_file:
                    st.download_button(
                        label="Download Generated PDF",
                        data=pdf_file,
                        file_name="generated_plan.pdf",
                        mime="application/pdf"
                    )

                # Step 2: Get analysis with custom prompt
                analysis_response = get_plan_analysis(gemini_api_key, output_pdf_path, custom_prompt)

                # Display analysis
                st.subheader("Plan Analysis")
                st.write(analysis_response)

            # Clean up temporary files
            if os.path.exists(image_path):
                os.remove(image_path)
            if os.path.exists(output_pdf_path):
                os.remove(output_pdf_path)

if __name__ == "__main__":
    main()