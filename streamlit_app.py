import streamlit as st
import pandas as pd
from data_manager import DataManager
from database import DatabaseManager
import urllib.parse
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import base64

def initialize_session_state():
    if 'cost_items' not in st.session_state:
        st.session_state.cost_items = []
    if 'total_cost' not in st.session_state:
        st.session_state.total_cost = 0.0
    if 'pre_discount_total' not in st.session_state:
        st.session_state.pre_discount_total = 0.0
    if 'data_manager' not in st.session_state:
        st.session_state.data_manager = DataManager()
    if 'db_manager' not in st.session_state:
        st.session_state.db_manager = DatabaseManager()
    if 'project_name' not in st.session_state:
        st.session_state.project_name = ""
    if 'show_project_options' not in st.session_state:
        st.session_state.show_project_options = True
    if 'groups' not in st.session_state:  # Store custom groups
        st.session_state.groups = []

def restore_project(uploaded_file):
    try:
        df = pd.read_csv(uploaded_file)
        st.session_state.cost_items = []

        # Extract project name if it exists
        if 'Project' in df.columns:
            st.session_state.project_name = df['Project'].iloc[0]
            df = df.drop('Project', axis=1)

        # Restore cost items
        for _, row in df.iterrows():
            unit_cost = float(row['Unit Cost (£)'])
            discount = float(row.get('Discount (%)', 0))  # Default to 0 if discount is missing
            discounted_cost = unit_cost * (1 - discount / 100)  # Calculate discounted cost
            total_cost = discounted_cost * int(row['Quantity'])  # Calculate total cost
            pre_discount_total = unit_cost * int(row['Quantity'])  # Calculate pre-discount total

            st.session_state.cost_items.append({
                'Manufacturer': row['Manufacturer'],
                'Product Type': row['Product Type'],
                'Product Code': row['Product Code'],
                'Description': row['Description'],
                'Unit Cost (£)': unit_cost,
                'Discount (%)': discount,
                'Discounted Cost (£)': discounted_cost,
                'Quantity': int(row['Quantity']),
                'Total (£)': total_cost,
                'Pre-Discount Total (£)': pre_discount_total,
                'Group': row.get('Group', 'Other'),  # Restore group if it exists
                'Supplier': row.get('Supplier', '')  # Restore supplier if it exists
            })

        # Update groups in session state
        groups_in_file = df['Group'].unique().tolist() if 'Group' in df.columns else []
        for group in groups_in_file:
            if group not in st.session_state.groups:
                st.session_state.groups.append(group)

        # Calculate totals
        st.session_state.total_cost = sum(item['Total (£)'] for item in st.session_state.cost_items)
        st.session_state.pre_discount_total = sum(item['Pre-Discount Total (£)'] for item in st.session_state.cost_items)
        st.session_state.show_project_options = False
        return True, "Project restored successfully"
    except Exception as e:
        return False, f"Error restoring project: {str(e)}"

def add_item(manufacturer, product_type, product_code, description, unit_cost, quantity, group, supplier, discount):
    # Check if item already exists in cost sheet
    existing_item = None
    for item in st.session_state.cost_items:
        if (item['Manufacturer'] == manufacturer and 
            item['Product Type'] == product_type and 
            item['Product Code'] == product_code and
            item['Group'] == group and
            item['Supplier'] == supplier):  # Check supplier as well
            existing_item = item
            break

    if existing_item:
        # Update existing item
        existing_item['Quantity'] += quantity
        existing_item['Total (£)'] = float(existing_item['Discounted Cost (£)'] * existing_item['Quantity'])
        existing_item['Pre-Discount Total (£)'] = float(existing_item['Unit Cost (£)'] * existing_item['Quantity'])
    else:
        # Add new item
        discounted_cost = unit_cost * (1 - discount / 100)  # Calculate discounted cost
        total = discounted_cost * quantity  # Calculate total cost
        pre_discount_total = unit_cost * quantity  # Calculate pre-discount total

        st.session_state.cost_items.append({
            'Manufacturer': manufacturer,
            'Product Type': product_type,
            'Product Code': product_code,
            'Description': description,
            'Unit Cost (£)': float(unit_cost),
            'Discount (%)': float(discount),
            'Discounted Cost (£)': float(discounted_cost),
            'Quantity': quantity,
            'Total (£)': float(total),
            'Pre-Discount Total (£)': float(pre_discount_total),
            'Group': group,  # Add group field
            'Supplier': supplier  # Add supplier field
        })

        # Add group to session state if it doesn't exist
        if group not in st.session_state.groups:
            st.session_state.groups.append(group)

    # Recalculate total cost and pre-discount total
    st.session_state.total_cost = sum(item['Total (£)'] for item in st.session_state.cost_items)
    st.session_state.pre_discount_total = sum(item['Pre-Discount Total (£)'] for item in st.session_state.cost_items)

def generate_google_search_url(manufacturer, product_code, description):
    # Construct a search query using manufacturer, product code, and description
    query = f"{manufacturer} {product_code} {description}"
    encoded_query = urllib.parse.quote_plus(query)
    return f"https://www.google.com/search?q={encoded_query}"

def create_pdf(project_name, cost_items, total_cost, pre_discount_total):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=20, rightMargin=20, topMargin=20, bottomMargin=20)
    elements = []

    # Styles
    styles = getSampleStyleSheet()
    title_style = styles["Heading1"]
    subtitle_style = styles["Heading2"]
    normal_style = styles["Normal"]

    # Custom styles
    total_style = ParagraphStyle(
        'TotalStyle',
        parent=styles['Heading2'],
        textColor=colors.darkblue,
        spaceAfter=12
    )

    group_style = ParagraphStyle(
        'GroupStyle',
        parent=styles['Heading3'],
        textColor=colors.darkslategray,
        spaceBefore=12,
        spaceAfter=6
    )

    # Add title
    if project_name:
        elements.append(Paragraph(f"Cost Estimation: {project_name}", title_style))
    else:
        elements.append(Paragraph("Cost Estimation", title_style))
    elements.append(Spacer(1, 0.25*inch))

    # Group items by group
    grouped_items = {}
    group_totals = {}
    group_pre_discount_totals = {}

    for item in cost_items:
        group = item['Group']
        if group not in grouped_items:
            grouped_items[group] = []
            group_totals[group] = 0
            group_pre_discount_totals[group] = 0

        grouped_items[group].append(item)
        group_totals[group] += item['Total (£)']
        group_pre_discount_totals[group] += item['Pre-Discount Total (£)']

    # Create a paragraph style for table cells that enables wrapping
    cell_style = ParagraphStyle(
        'CellStyle',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,  # Line spacing
        spaceBefore=1,
        spaceAfter=1
    )

    # Add group tables
    for group, items in grouped_items.items():
        # Add group header
        elements.append(Paragraph(f"Group: {group}", group_style))

        # Prepare data for table
        headers = ["Product Code", "Manufacturer", "Description", "Unit Cost (£)", "Discount (%)", 
                  "Discounted (£)", "Qty", "Total (£)", "Pre-Disc Total (£)"]

        # Create Paragraph objects for headers to enable wrapping
        header_paragraphs = [Paragraph(header, ParagraphStyle('HeaderStyle', parent=cell_style, fontName='Helvetica-Bold')) for header in headers]
        data = [header_paragraphs]

        for item in items:
            # Convert description to Paragraph to enable wrapping
            desc_paragraph = Paragraph(item['Description'], cell_style)

            # Create paragraphs for numeric values to ensure proper alignment
            unit_cost = Paragraph(f"{item['Unit Cost (£)']:.2f}", cell_style)
            discount = Paragraph(f"{item['Discount (%)']:.2f}", cell_style)
            discounted = Paragraph(f"{item['Discounted Cost (£)']:.2f}", cell_style)
            quantity = Paragraph(str(item['Quantity']), cell_style)
            total = Paragraph(f"{item['Total (£)']:.2f}", cell_style)
            pre_disc_total = Paragraph(f"{item['Pre-Discount Total (£)']:.2f}", cell_style)

            # Other values as paragraphs too for consistent styling
            product_code = Paragraph(item['Product Code'], cell_style)
            manufacturer = Paragraph(item['Manufacturer'], cell_style)

            data.append([
                product_code,
                manufacturer,
                desc_paragraph,
                unit_cost,
                discount,
                discounted,
                quantity,
                total,
                pre_disc_total
            ])

        # Add group summary row
        group_total = Paragraph(f"{group_totals[group]:.2f}", ParagraphStyle('TotalStyle', parent=cell_style, fontName='Helvetica-Bold'))
        group_pre_disc = Paragraph(f"{group_pre_discount_totals[group]:.2f}", ParagraphStyle('TotalStyle', parent=cell_style, fontName='Helvetica-Bold'))
        group_total_label = Paragraph("Group Total:", ParagraphStyle('TotalStyle', parent=cell_style, fontName='Helvetica-Bold'))

        data.append([
            Paragraph("", cell_style), 
            Paragraph("", cell_style), 
            Paragraph("", cell_style), 
            Paragraph("", cell_style), 
            Paragraph("", cell_style), 
            Paragraph("", cell_style), 
            group_total_label,
            group_total,
            group_pre_disc
        ])

        # Calculate column widths - adjust these to fit the page
        available_width = doc.width
        col_widths = [
            available_width * 0.1,   # Product Code
            available_width * 0.12,  # Manufacturer
            available_width * 0.25,  # Description - give more space
            available_width * 0.08,  # Unit Cost
            available_width * 0.08,  # Discount
            available_width * 0.08,  # Discounted
            available_width * 0.05,  # Qty - smaller
            available_width * 0.12,  # Total
            available_width * 0.12   # Pre-Disc Total
        ]

        # Create table with specified column widths
        table = Table(data, repeatRows=1, colWidths=col_widths)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -2), 0.5, colors.grey),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
            ('LINEBELOW', (0, 0), (-1, 0), 1, colors.black),
            ('ALIGN', (3, 1), (8, -1), 'RIGHT'),  # Align numeric columns to the right
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # Center content vertically
        ]))
        elements.append(table)
        elements.append(Spacer(1, 0.2*inch))

    # Overall totals
    elements.append(Spacer(1, 0.1*inch))
    elements.append(Paragraph("Overall Totals", subtitle_style))

    # Total savings calculation
    total_savings = pre_discount_total - total_cost
    savings_percentage = (total_savings / pre_discount_total * 100) if pre_discount_total > 0 else 0

    # Create totals table with Paragraphs for consistent styling
    totals_data = [
        [Paragraph("Total Cost (After Discounts)", cell_style), Paragraph(f"£{total_cost:,.2f}", cell_style)],
        [Paragraph("Pre-Discount Total Cost", cell_style), Paragraph(f"£{pre_discount_total:,.2f}", cell_style)],
        [Paragraph("Total Savings", cell_style), Paragraph(f"£{total_savings:,.2f} ({savings_percentage:.1f}%)", cell_style)]
    ]

    totals_table = Table(totals_data, colWidths=[3*inch, 2*inch])
    totals_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
    ]))

    elements.append(totals_table)

    # Add generated date
    elements.append(Spacer(1, 0.5*inch))
    elements.append(Paragraph(f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}", normal_style))

    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer


def get_download_link_for_pdf(pdf, filename):
    """Generate a link to download the pdf file"""
    b64 = base64.b64encode(pdf.read()).decode()
    href = f'<a href="data:application/pdf;base64,{b64}" download="{filename}">Download PDF</a>'
    return href
    

def main():
    st.title("Project Cost Estimation Tool")

    initialize_session_state()
    data_manager = st.session_state.data_manager
    db_manager = st.session_state.db_manager

    if st.session_state.show_project_options:
        st.write("Welcome! Please choose an option:")
        col1, col2 = st.columns(2)

        with col1:
            if st.button("Create New Project"):
                st.session_state.show_project_options = False
                st.rerun()

        with col2:
            uploaded_file = st.file_uploader("Restore Existing Project", type=['csv'])
            if uploaded_file is not None:
                success, message = restore_project(uploaded_file)
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)

        st.stop()

    # Catalog Management Section with tabs
    st.sidebar.title("Catalog Management")
    catalog_action = st.sidebar.radio(
        "Select Action",
        ["Add New Product", "Import Catalog"]
    )

    if catalog_action == "Add New Product":
        st.sidebar.subheader("Add New Product")
        with st.sidebar.form("add_product"):
            manufacturer = st.text_input("Manufacturer")
            product_type = st.text_input("Product Type")
            description = st.text_input("Description")
            product_code = st.text_input("Product Code")
            unit_cost = st.number_input("Unit Cost (£)", min_value=0.0, step=0.01)
            supplier = st.text_input("Supplier", placeholder="Enter supplier name...")
            discount = st.number_input("Discount (%)", min_value=0.0, max_value=100.0, value=0.0, step=1.0)

            if st.form_submit_button("Add Product"):
                success, message = db_manager.add_product({
                    'manufacturer': manufacturer,
                    'product_type': product_type,
                    'description': description,
                    'product_code': product_code,
                    'unit_cost': unit_cost,
                    'supplier': supplier,
                    'discount': discount
                })
                if success:
                    st.sidebar.success(message)
                else:
                    st.sidebar.error(message)

    elif catalog_action == "Import Catalog":
                st.sidebar.subheader("Import Catalog")
                st.sidebar.write("Required columns: manufacturer, product_type, description, product_code, unit_cost, supplier (optional), discount (optional)")

                # Add a download button for the import template
                template_df = pd.DataFrame(columns=[
                    'manufacturer', 'product_type', 'description', 'product_code', 'unit_cost', 'supplier', 'discount'
                ])
                csv = template_df.to_csv(index=False)
                st.sidebar.download_button(
                    "Download Import Template",
                    csv,
                    "catalog_import_template.csv",
                    "text/csv",
                    key='download-template'
                )

                uploaded_file = st.sidebar.file_uploader("Choose a file", type=['xlsx', 'csv'])

                if uploaded_file is not None:
                    success, message = data_manager.import_catalog(uploaded_file)
                    if success:
                        st.sidebar.success(message)
                    else:
                        st.sidebar.error(message)

    # Main content area - Product Selection and Cost Sheet
    st.subheader("Add New Item")
    col1, col2 = st.columns(2)

    with col1:
        manufacturer = st.selectbox(
            "Select Manufacturer",
            options=data_manager.get_manufacturers(),
            key="manufacturer",
            placeholder="Search manufacturer...",
            index=None
        )

        product_type = st.selectbox(
            "Select Product Type",
            options=data_manager.get_product_types(manufacturer) if manufacturer else [],
            key="product_type",
            placeholder="Search product type...",
            index=None
        )

    with col2:
        description = st.selectbox(
            "Select Product Description",
            options=data_manager.get_product_descriptions(manufacturer, product_type) if manufacturer and product_type else [],
            key="product_desc",
            placeholder="Search description...",
            index=None
        )

        if description:
            product_details = data_manager.get_product_details_by_description(
                manufacturer, 
                product_type, 
                description
            )

            if product_details:
                st.text_input("Product Code", value=product_details['product_code'], disabled=True)
                unit_cost = st.number_input("Unit Cost (£)", value=float(product_details['unit_cost']), disabled=True)
                discount = st.number_input("Discount (%)", value=float(product_details.get('discount', 0)), disabled=True)
                discounted_cost = unit_cost * (1 - discount / 100)  # Calculate discounted cost
                st.text_input("Discounted Cost (£)", value=f"{discounted_cost:.2f}", disabled=True)
                quantity = st.number_input("Quantity", min_value=1, value=1, step=1)

                # Group selection and new group input
                col1, col2 = st.columns(2)  # Two columns for better spacing
                with col1:
                    group = st.selectbox(
                        "Select Group",
                        options=st.session_state.groups,  # Existing groups
                        index=None,  # No default selection
                        placeholder="Select a group...",
                        key="group_select"
                    )
                with col2:
                    new_group = st.text_input(
                        "Enter New Group Name",
                        placeholder="Type a new group...",
                        key="new_group_input"
                    )

                # Determine the final group value
                if new_group:  # If the user types a new group, use that
                    group = new_group
                    if group not in st.session_state.groups:  # Add new group to session state
                        st.session_state.groups.append(group)
                elif not group:  # If no group is selected or typed, show an error
                    st.error("Please select or type a group.")

                col1, col2 = st.columns(2)

                with col1:
                    if st.button("Add to Cost Sheet"):
                        if not group:
                            st.error("Please select or type a group.")
                        else:
                            add_item(
                                manufacturer,
                                product_type,
                                product_details['product_code'],
                                product_details['description'],
                                product_details['unit_cost'],
                                quantity,
                                group,  # Pass group to add_item
                                product_details.get('supplier', ''),  # Pass supplier to add_item
                                product_details.get('discount', 0)  # Pass discount to add_item
                            )
                            st.rerun()

                with col2:
                    search_url = generate_google_search_url(
                        manufacturer,
                        product_details['product_code'],
                        product_details['description']
                    )
                    st.markdown(
                        f'<a href="{search_url}" target="_blank" style="text-decoration: none;">'
                        f'<button style="width: 100%; height: 40px; background-color: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer;">Search Online</button>'
                        f'</a>',
                        unsafe_allow_html=True
                    )

    # Cost sheet display
    if st.session_state.cost_items:
        st.subheader("Cost Sheet")

        # Group items by their 'Group' field
        grouped_items = {}
        group_totals = {}
        group_pre_discount_totals = {}

        for item in st.session_state.cost_items:
            group = item['Group']
            if group not in grouped_items:
                grouped_items[group] = []
                group_totals[group] = 0
                group_pre_discount_totals[group] = 0

            grouped_items[group].append(item)
            group_totals[group] += item['Total (£)']
            group_pre_discount_totals[group] += item['Pre-Discount Total (£)']

        # Display each group in an expander
        for group, items in grouped_items.items():
            with st.expander(f"Group: {group} - Total: £{group_totals[group]:,.2f} | Pre-Discount Total: £{group_pre_discount_totals[group]:,.2f}"):
                # Create a DataFrame for the group
                df = pd.DataFrame(items)

                # Add a "Delete" button for each row
                df["Delete"] = False  # Add a column for the delete checkbox

                # Display the DataFrame with an editable "Quantity" column
                edited_df = st.data_editor(
                    df,
                    column_config={
                        "Quantity": st.column_config.NumberColumn(
                            "Quantity",
                            min_value=1,
                            step=1,
                        ),
                        "Delete": st.column_config.CheckboxColumn(
                            "Delete?",
                            help="Check to delete this item",
                            default=False,
                        ),
                    },
                    hide_index=True,
                    disabled=["Manufacturer", "Product Type", "Product Code", "Description", "Unit Cost (£)", "Discount (%)", 
                             "Discounted Cost (£)", "Total (£)", "Pre-Discount Total (£)", "Group", "Supplier"]
                )

                # Handle deletions
                if st.button(f"Delete Selected Items in {group}", key=f"delete_{group}"):
                    # Filter out items marked for deletion
                    items_to_keep = [item for item, to_delete in zip(items, edited_df["Delete"]) if not to_delete]
                    st.session_state.cost_items = [item for item in st.session_state.cost_items if item not in items or item in items_to_keep]
                    st.session_state.total_cost = sum(item['Total (£)'] for item in st.session_state.cost_items)
                    st.session_state.pre_discount_total = sum(item['Pre-Discount Total (£)'] for item in st.session_state.cost_items)
                    st.success(f"Deleted selected items in {group}!")
                    st.rerun()

                # Update quantities for the group
                for i, row in edited_df.iterrows():
                    for item in st.session_state.cost_items:
                        if item['Product Code'] == row['Product Code'] and item['Group'] == group:
                            if item['Quantity'] != row['Quantity']:  # Only update if quantity changed
                                item['Quantity'] = row['Quantity']
                                item['Total (£)'] = row['Quantity'] * item['Discounted Cost (£)']
                                item['Pre-Discount Total (£)'] = row['Quantity'] * item['Unit Cost (£)']

                # Recalculate totals
                st.session_state.total_cost = sum(item['Total (£)'] for item in st.session_state.cost_items)
                st.session_state.pre_discount_total = sum(item['Pre-Discount Total (£)'] for item in st.session_state.cost_items)

        # Display overall totals
        st.subheader("Overall Totals")
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"Total Cost (After Discounts): £{st.session_state.total_cost:,.2f}")
        with col2:
            st.write(f"Pre-Discount Total Cost: £{st.session_state.pre_discount_total:,.2f}")

        # Calculate total savings
        total_savings = st.session_state.pre_discount_total - st.session_state.total_cost
        savings_percentage = (total_savings / st.session_state.pre_discount_total * 100) if st.session_state.pre_discount_total > 0 else 0
        st.write(f"Total Savings: £{total_savings:,.2f} ({savings_percentage:.1f}%)")

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Clear Cost Sheet"):
                st.session_state.cost_items = []
                st.session_state.total_cost = 0.0
                st.session_state.pre_discount_total = 0.0
                st.rerun()

        with col2:
            if st.session_state.cost_items:
                project_name = st.text_input("Project Name", value=st.session_state.project_name, key="project_name_input").strip()
                st.session_state.project_name = project_name

                df = pd.DataFrame(st.session_state.cost_items)
                try:
                    # Reorder columns to place 'Group' as the first column
                    columns_order = ['Group', 'Supplier'] + [col for col in df.columns if col not in ['Group', 'Supplier']]
                    df = df[columns_order]

                    # Export to CSV
                    csv = df.to_csv(index=False)
                    filename = "cost_estimation.csv"
                    if project_name:
                        # Remove any special characters that could cause issues
                        safe_project_name = "".join(c for c in project_name if c.isalnum() or c in (' ', '_', '-'))
                        filename = f"{safe_project_name}_estimation.csv"

                    st.download_button(
                        "Export to CSV",
                        csv,
                        filename,
                        "text/csv",
                        key='download-csv'
                    )
                except Exception as e:
                    st.error(f"Error preparing export: {str(e)}")

        with col3:
            if st.session_state.cost_items:
                # Generate PDF export
                pdf_filename = "cost_estimation.pdf"
                if st.session_state.project_name:
                    safe_project_name = "".join(c for c in st.session_state.project_name if c.isalnum() or c in (' ', '_', '-'))
                    pdf_filename = f"{safe_project_name}_estimation.pdf"

                try:
                    pdf_buffer = create_pdf(
                        st.session_state.project_name,
                        st.session_state.cost_items,
                        st.session_state.total_cost,
                        st.session_state.pre_discount_total
                    )

                    st.download_button(
                        "Export to PDF",
                        pdf_buffer,
                        pdf_filename,
                        "application/pdf",
                        key='download-pdf'
                    )
                except Exception as e:
                    st.error(f"Error generating PDF: {str(e)}")

if __name__ == "__main__":
    main()