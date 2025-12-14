import os
import re
try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True

    class PDF(FPDF):
        """Custom PDF class to handle headers and footers."""
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.font_family_main = 'Arial' 

        def header(self):
            pass 

        def footer(self):
            self.set_y(-15)
            self.set_font(self.font_family_main, '', 8)
            self.cell(0, 10, 'Page ' + str(self.page_no()), 0, 0, 'C')

except ImportError:
    FPDF_AVAILABLE = False
    FPDF = None 
    PDF = None

def strip_html_tags(text):
    if not text:
        return ""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

def _setup_pdf_fonts(pdf, font_path, logger=print):
    """Helper to setup fonts for the PDF instance."""
    bold_font_path = ""
    default_font = 'Arial'
    
    if font_path:
        bold_font_path = font_path.replace("DejaVuSans.ttf", "DejaVuSans-Bold.ttf")

    try:
        if font_path and os.path.exists(font_path): 
            pdf.add_font('DejaVu', '', font_path, uni=True)
            default_font = 'DejaVu'
            if os.path.exists(bold_font_path): 
                pdf.add_font('DejaVu', 'B', bold_font_path, uni=True)
            else:
                pdf.add_font('DejaVu', 'B', font_path, uni=True)
    except Exception as font_error:
        logger(f"   ⚠️ Could not load DejaVu font: {font_error}. Falling back to Arial.")
        default_font = 'Arial'
    
    pdf.font_family_main = default_font
    return default_font

def add_metadata_page(pdf, post, font_family):
    """Adds a dedicated metadata page to the PDF with clickable links."""
    pdf.add_page()
    pdf.set_font(font_family, 'B', 16)
    pdf.multi_cell(w=0, h=10, txt=post.get('title', 'Untitled Post'), align='C')
    pdf.ln(10)
    pdf.set_font(font_family, '', 11)
    
    def add_info_row(label, value, link_url=None):
        if not value: return
        
        # Write Label (Bold)
        pdf.set_font(font_family, 'B', 11)
        pdf.write(8, f"{label}: ")
        
        # Write Value
        if link_url:
            # Styling for clickable link: Blue + Underline
            pdf.set_text_color(0, 0, 255)
            # Check if font supports underline style directly or just use 'U'
            # FPDF standard allows 'U' in style string.
            # We use 'U' combined with the font family. 
            # Note: DejaVu implementation in fpdf2 might handle 'U' automatically or ignore it depending on version,
            # but setting text color indicates link clearly enough usually.
            pdf.set_font(font_family, 'U', 11) 
            
            # Pass the URL to the 'link' parameter
            pdf.multi_cell(w=0, h=8, txt=str(value), link=link_url)
            
            # Reset styles
            pdf.set_text_color(0, 0, 0)
            pdf.set_font(font_family, '', 11)
        else:
            pdf.set_font(font_family, '', 11)
            pdf.multi_cell(w=0, h=8, txt=str(value))
            
        pdf.ln(2)

    date_str = post.get('published') or post.get('added') or 'Unknown'
    add_info_row("Date Uploaded", date_str)
    
    creator = post.get('creator_name') or post.get('user') or 'Unknown'
    add_info_row("Creator", creator)
    
    add_info_row("Service", post.get('service', 'Unknown'))
    
    link = post.get('original_link')
    if not link and post.get('service') and post.get('user') and post.get('id'):
        link = f"https://kemono.su/{post['service']}/user/{post['user']}/post/{post['id']}"
    
    # Pass 'link' as both the text value AND the URL target
    add_info_row("Original Link", link, link_url=link)
    
    tags = post.get('tags')
    if tags:
        tags_str = ", ".join(tags) if isinstance(tags, list) else str(tags)
        add_info_row("Tags", tags_str)

    pdf.ln(10)
    pdf.cell(0, 0, border='T') 
    pdf.ln(10)

def create_individual_pdf(post_data, output_filename, font_path, add_info_page=False, add_comments=False, logger=print):
    """
    Creates a PDF for a single post.
    Supports optional metadata page and appending comments.
    """
    if not FPDF_AVAILABLE:
        logger("❌ PDF Creation failed: 'fpdf2' library not installed.")
        return False

    pdf = PDF()
    font_family = _setup_pdf_fonts(pdf, font_path, logger)
    
    if add_info_page:
        # add_metadata_page adds the page start itself
        add_metadata_page(pdf, post_data, font_family)
        # REMOVED: pdf.add_page() <-- This ensures content starts right below the line
    else:
        pdf.add_page()

    # Only add the Title header manually if we didn't add the info page
    # (Because the info page already contains the title at the top)
    if not add_info_page:
        pdf.set_font(font_family, 'B', 16)
        pdf.multi_cell(w=0, h=10, txt=post_data.get('title', 'Untitled Post'), align='L')
        pdf.ln(5)

    content_text = post_data.get('content_text_for_pdf')
    comments_list = post_data.get('comments_list_for_pdf')

    # 1. Write Content
    if content_text:
        pdf.set_font(font_family, '', 12)
        pdf.multi_cell(w=0, h=7, txt=content_text)
        pdf.ln(10)

    # 2. Write Comments (if enabled and present)
    if comments_list and (add_comments or not content_text):
        if add_comments and content_text:
             pdf.add_page()
             pdf.set_font(font_family, 'B', 14)
             pdf.cell(0, 10, "Comments", ln=True)
             pdf.ln(5)

        for i, comment in enumerate(comments_list):
            user = comment.get('commenter_name', 'Unknown User')
            timestamp = comment.get('published', 'No Date')
            body = strip_html_tags(comment.get('content', ''))

            pdf.set_font(font_family, '', 10)
            pdf.write(8, "Comment by: ")
            pdf.set_font(font_family, 'B', 10)
            pdf.write(8, str(user))
            
            pdf.set_font(font_family, '', 10)
            pdf.write(8, f" on {timestamp}")
            pdf.ln(10)

            pdf.set_font(font_family, '', 11)
            pdf.multi_cell(w=0, h=7, txt=body)
            
            if i < len(comments_list) - 1:
                pdf.ln(3)
                pdf.cell(w=0, h=0, border='T')
                pdf.ln(3)
    
    try:
        pdf.output(output_filename)
        return True
    except Exception as e:
        logger(f"❌ Error saving PDF '{os.path.basename(output_filename)}': {e}")
        return False

def create_single_pdf_from_content(posts_data, output_filename, font_path, add_info_page=False, logger=print):
    """
    Creates a single, continuous PDF from multiple posts.
    """
    if not FPDF_AVAILABLE:
        logger("❌ PDF Creation failed: 'fpdf2' library is not installed.")
        return False

    if not posts_data:
        logger("   No text content was collected to create a PDF.")
        return False

    pdf = PDF()
    font_family = _setup_pdf_fonts(pdf, font_path, logger)
    
    logger(f"   Starting continuous PDF creation with content from {len(posts_data)} posts...")

    for i, post in enumerate(posts_data):
        if add_info_page:
            add_metadata_page(pdf, post, font_family)
            # REMOVED: pdf.add_page() <-- This ensures content starts right below the line
        else:
            pdf.add_page()

        if not add_info_page:
            pdf.set_font(font_family, 'B', 16)
            pdf.multi_cell(w=0, h=10, txt=post.get('title', 'Untitled Post'), align='L')
            pdf.ln(5)

        if 'comments' in post and post['comments']:
            comments_list = post['comments']
            for comment_index, comment in enumerate(comments_list):
                user = comment.get('commenter_name', 'Unknown User')
                timestamp = comment.get('published', 'No Date')
                body = strip_html_tags(comment.get('content', ''))

                pdf.set_font(font_family, '', 10)
                pdf.write(8, "Comment by: ")
                if user is not None:
                    pdf.set_font(font_family, 'B', 10)
                    pdf.write(8, str(user))
                
                pdf.set_font(font_family, '', 10)
                pdf.write(8, f" on {timestamp}")
                pdf.ln(10)

                pdf.set_font(font_family, '', 11)
                pdf.multi_cell(w=0, h=7, txt=body)
                
                if comment_index < len(comments_list) - 1:
                    pdf.ln(3)
                    pdf.cell(w=0, h=0, border='T')
                    pdf.ln(3)
        elif 'content' in post:
            pdf.set_font(font_family, '', 12)
            pdf.multi_cell(w=0, h=7, txt=post.get('content', 'No Content'))
    
    try:
        pdf.output(output_filename)
        logger(f"✅ Successfully created single PDF: '{os.path.basename(output_filename)}'")
        return True
    except Exception as e:
        logger(f"❌ A critical error occurred while saving the final PDF: {e}")
        return False