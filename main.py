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
    master_plan_llm_prompt_text = """As the builder of this property, your task is to generate a description of this master plan. Extract and present information from the provided PDF. Be concise, direct, and factual, adhering strictly to what is visibly presented or explicitly stated in the master plan sections, without assumptions or excessive synonyms. Utilize the detailed views from pages 2-5.I want meaning full description which is attract to buyers but do it in simple and natural language.

        PDF Structure Overview:
        Page 1: Full master plan view.
        Page 2: Focus on the upper-left quadrant.
        Page 3: Focus on the upper-right quadrant.
        Page 4: Focus on the lower-left quadrant.
        Page 5: Focus on the lower-right quadrant.

        Present the master plan's features by describing the following points. 
        Focus on rigorous, eye-catching details.
        Project Scope: State the total land area, number of units, and number of towers. Mention project launch and completion dates if visible.
        Land Use & Density: Identify and specify designated zones (e.g., residential, commercial, open spaces) and their visible allocations or percentages. State units per acre.
        Connectivity & Access: Detail visible internal road networks, primary access points, and any significant external connectivity features. Mention widths if indicated.
        On-Site Features & Amenities: List all explicitly drawn or labeled amenities (e.g., clubhouse, parks, sports courts, specific utility placements). State any visible area sizes for these features.( i just want 3-4 meaningfull bullet points.)
        Key Dimensions & Figures: Provide any other directly stated measurements, capacities, or distinguishing numerical facts about the master plan components.( i just want 3-4 meaningfull bullet points.)

        Note: Don't mention you get this info from master plan, just explain the things like you are the seller of this project."""

    floor_plan_llm_prompt_text = """As the builder of this property, your task is to sell this floor plan. Extract and present information from the provided PDF. Be concise, direct, and factual, adhering strictly to what is visibly presented or explicitly stated in the floor plan, without assumptions or excessive synonyms. Dont mention sizes in bulletpoints. Just write simple and meaningfull sentance. I want just 3-4 bullet point in response.

        PDF Structure Overview:
        Page 1: Full floor plan view.
        Page 2: Focus on the upper-left quadrant.
        Page 3: Focus on the upper-right quadrant.
        Page 4: Focus on the lower-left quadrant.
        Page 5: Focus on the lower-right quadrant.
        
        Write in plain English with short sentences.
        Be direct and concise.
        Use a natural, conversational tone (contractions ok; starting with ‘And/But’ is fine).
        Avoid hype, clichés, and marketing speak.
        Cut adverbs and filler.
        Prefer active voice.
        
        An sample format of output is this:
        Expected Floor plan output

        Smartly designed layout with zero space wastage and cross-ventilation in all rooms

        Master bedroom with attached balcony overlooking landscaped greens

        Open kitchen with dining space optimized for modern living


        or 

        Spacious living-dining area opening to a wide balcony for natural light & fresh air

        Master Bedroom with walk-in wardrobe and attached bath for added privacy

        Separate utility & storage space for efficient home management"""

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