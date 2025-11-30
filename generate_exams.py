import json
import os
import sys
import textwrap
from PIL import Image, ImageDraw, ImageFont
import qrcode 
import arabic_reshaper
from bidi.algorithm import get_display

# --- الإعدادات الأساسية والثوابت ---
JSON_FILE = 'jsonQ.json' 
OUTPUT_DIR = 'exam_sheets_output_images'
FONT_PATH = 'NotoKufiArabic-Regular.ttf' 

# أبعاد ورقة A4 بالبيكسل (تقريباً عند 150 DPI)
WIDTH, HEIGHT = 1240, 1754
MARGIN = 70 

# قائمة الحروف للخيار
OPTION_LETTERS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']

# إنشاء مجلد الإخراج إذا لم يكن موجوداً
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# --- دوال المساعدة (نفسها) ---

def load_exam_data(file_path):
    """قراءة وتحليل بيانات الامتحان من ملف JSON."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            full_data = json.load(f)
        return full_data.get('data', {})
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"❌ خطأ في قراءة ملف JSON: {e}")
        return {}

def generate_qrcode(data_to_encode, output_path):
    """إنشاء وحفظ رمز الاستجابة السريعة (QR Code) كملف صورة PNG."""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=6,
            border=4,
        )
        qr.add_data(data_to_encode)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        
        img.save(output_path)
        display_text = data_to_encode if len(data_to_encode) < 100 else f"{data_to_encode[:100]}..."
        print(f"✅ تم إنشاء QR Code بنجاح. البيانات المشفرة: {display_text}")
        return True
    except Exception as e:
        print(f"❌ خطأ في إنشاء QR Code: {e}")
        return False

def fix_arabic_text(text):
    """
    تقوم بتوصيل الأحرف العربية وعكس ترتيب النص ليناسب الطباعة من اليمين إلى اليسار.
    """
    if not text:
        return ""
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)
    return bidi_text

def get_text_metrics(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]

def draw_header(img, draw, exam_info, user_data, qrcode_path, font_large, font_medium, cursor_y, is_first_page):
    """رسم رأس الصفحة الذي يحتوي على العنوان وتفاصيل الطالب ورمز الاستجابة السريعة (QR Code)."""
    
    subject_name = exam_info.get('subject_name', 'امتحان غير محدد')
    stage = exam_info.get('stage', 'N/A')
    model_type = user_data.get('model_type', exam_info.get('model_type', 'N/A'))
    
    if is_first_page:
        
        # 1. العنوان الرئيسي
        header_text = f"ورقة امتحان: {subject_name} - المرحلة: {stage}"
        processed_header = fix_arabic_text(header_text)
        
        text_width, text_height = get_text_metrics(draw, processed_header, font_large)
        draw.text(((WIDTH - text_width) / 2, cursor_y), processed_header, fill='black', font=font_large)
        cursor_y += text_height + 20 
        
        # 2. تفاصيل الطالبة
        student_name = user_data.get('name', 'غير متوفر')
        student_id = user_data.get('id', 'غير متوفر')
        
        details_x_ref = WIDTH - MARGIN

        details = [
            f"اسم الطالب: {student_name}",
            f"رقم الطالب: {student_id}",
            f"نموذج الأسئلة: {model_type}"
        ]
        
        for detail in details:
            processed_detail = fix_arabic_text(detail)
            
            text_width, text_height = get_text_metrics(draw, processed_detail, font_medium)

            draw.text((details_x_ref - text_width, cursor_y), processed_detail, fill='black', font=font_medium)
            cursor_y += text_height + 8 

        # 3. وضع رمز الاستجابة السريعة (QR Code)
        if os.path.exists(qrcode_path):
            try:
                qrcode_img = Image.open(qrcode_path).convert("RGBA")
                qrcode_size = 150 
                qrcode_img = qrcode_img.resize((qrcode_size, qrcode_size))
                
                qrcode_x = MARGIN
                qrcode_y = MARGIN + 10

                img.paste(qrcode_img, (qrcode_x, qrcode_y), qrcode_img)
                
                qrcode_bottom_y = qrcode_y + qrcode_size
                cursor_y = max(cursor_y, qrcode_bottom_y) + 20 
                
            except Exception as e:
                print(f"❌ فشل في دمج صورة QR Code: {e}")
        
    else:
        cursor_y = MARGIN + 30 
        
    cursor_y += 15 
    return cursor_y

def create_student_exam_image(exam_info, user_data, output_filename, qrcode_path):
    """إنشاء ورقة امتحان كصورة PNG (صفحة الأسئلة)."""
    
    # 1. إعداد الخطوط
    try:
        font_large = ImageFont.truetype(FONT_PATH, 40)
        font_medium = ImageFont.truetype(FONT_PATH, 30)
        font_small = ImageFont.truetype(FONT_PATH, 24)
    except IOError as e:
        print(f"\n\n🛑 خطأ فادح: فشل في تحميل الخط العربي. تأكد من أن الملف '{FONT_PATH}' موجود في نفس المجلد.")
        if not os.path.exists(FONT_PATH):
            print(f"🛑 الملف '{FONT_PATH}' غير موجود. يرجى تحميله ووضعه في نفس مجلد السكربت.")
        sys.exit(1)

    questions = user_data.get('exam', [])
    content_width = WIDTH - 2 * MARGIN
    question_num = 1
    page_num = 1
    
    img = Image.new('RGB', (WIDTH, HEIGHT), color='white')
    draw = ImageDraw.Draw(img)
    cursor_y = MARGIN
    cursor_y = draw_header(img, draw, exam_info, user_data, qrcode_path, font_large, font_medium, cursor_y, is_first_page=True)
    
    images_to_save = []
    
    for q_item in questions:
        
        q_text = q_item.get('question_text', {}).get('text', 'نص السؤال غير متوفر')
        q_type = q_item.get('question_type_translation', 'N/A')
        
        chars_per_line = int(content_width / font_small.size * 0.7) 
        question_lines = textwrap.wrap(fix_arabic_text(f"{question_num}. ({q_type}) {q_text}"), width=chars_per_line)
        question_height_est = len(question_lines) * 30 
        
        options_height_est = 0
        options = q_item.get('options', [])
        if options:
            options_lines = (len(options) + 1) // 2 
            options_height_est = options_lines * 35 
            
        estimated_total_height = question_height_est + options_height_est + 50 

        if cursor_y + estimated_total_height > HEIGHT - MARGIN: 
            images_to_save.append(img.copy())
            
            page_num += 1
            img = Image.new('RGB', (WIDTH, HEIGHT), color='white')
            draw = ImageDraw.Draw(img)
            cursor_y = MARGIN
            
            cursor_y = draw_header(img, draw, exam_info, user_data, qrcode_path, font_large, font_medium, cursor_y, is_first_page=False)

        # 1. طباعة نص السؤال
        question_line = f"{question_num}. ({q_type}) {q_text}"
        processed_question = fix_arabic_text(question_line)
        
        wrapped_text = textwrap.wrap(processed_question, width=chars_per_line)
        
        for line in wrapped_text:
            text_width, text_height = get_text_metrics(draw, line, font_small)
            draw.text((WIDTH - MARGIN - text_width, cursor_y), line, fill='black', font=font_small)
            cursor_y += text_height + 3 

        # 2. طباعة الخيارات
        if options:
            col_width = content_width / 2 
            _, option_height = get_text_metrics(draw, fix_arabic_text("مثال"), font_small)
            
            cursor_y += 5 
            
            for j, opt in enumerate(options):
                option_text = opt.get('text', 'خيار غير متوفر')
                
                if j < len(OPTION_LETTERS):
                    option_letter = OPTION_LETTERS[j]
                else:
                    option_letter = chr(65 + j)
                
                prefix = f"({option_letter}) "
                
                processed_option_text = fix_arabic_text(prefix + option_text)
                text_width, _ = get_text_metrics(draw, processed_option_text, font_small)
                
                padding = 15
                if j % 2 == 0:
                    col_end_x = WIDTH - MARGIN 
                    text_x = col_end_x - text_width - padding
                    draw.text((text_x, cursor_y), processed_option_text, fill='black', font=font_small)
                else:
                    col_end_x = WIDTH - MARGIN - col_width 
                    text_x = col_end_x - text_width - padding
                    draw.text((text_x, cursor_y), processed_option_text, fill='black', font=font_small)
                
                if (j + 1) % 2 == 0:
                    cursor_y += option_height + 8
                elif j == len(options) - 1:
                    cursor_y += option_height + 8
            
            if len(options) % 2 != 0:
                cursor_y += 5 
        
        cursor_y += 15
        question_num += 1

    images_to_save.append(img.copy())
    
    successful = True
    for i, final_img in enumerate(images_to_save):
        final_output_filename = output_filename.replace('.png', f'_Questions_Page_{i+1}.png')
        try:
            final_img.save(final_output_filename)
        except Exception as e:
            print(f"❌ فشل في إخراج الصورة لملف {final_output_filename}: {e}")
            successful = False
            
    if len(images_to_save) > 1:
        print(f"🎉 تم توزيع الـ {len(questions)} سؤالاً بنجاح على {len(images_to_save)} صفحة.")

    return successful

def create_bubble_sheet_image(exam_info, user_data, output_filename, qrcode_path):
    """
    🔥 إصدار مصحح من Bubble Sheet - متوافق مع كود المسح الضوئي
    يضيف ID فريدًا لكل فقاعة ويسجل إحداثياتها في ملف JSON.
    """

    # 1. إعداد الخطوط
    try:
        font_large = ImageFont.truetype(FONT_PATH, 40)
        font_medium = ImageFont.truetype(FONT_PATH, 30)
        font_small = ImageFont.truetype(FONT_PATH, 24)
    except IOError as e:
        print(f"\n\n🛑 خطأ فادح: فشل في تحميل الخط العربي.")
        sys.exit(1)

    # 2. إعداد الصورة والرسام
    img = Image.new('RGB', (WIDTH, HEIGHT), color='white')
    draw = ImageDraw.Draw(img)
    cursor_y = MARGIN
    
    # رسم رأس الصفحة
    cursor_y = draw_header(img, draw, exam_info, user_data, qrcode_path, font_large, font_medium, cursor_y, is_first_page=True)
    
    questions = user_data.get('exam', [])
    num_questions = len(questions)
    
    # --- إعدادات الأعمدة والفقاعات ---
    MAX_OPTIONS = 4 
    QUESTIONS_PER_COLUMN = 20 
    NUM_COLUMNS = 3 
    
    available_width = WIDTH - 2 * MARGIN
    column_width = available_width / NUM_COLUMNS 
    
    bubble_radius = 20 
    bubble_x_spacing = 15
    q_num_label_width = 80 
    
    # قائمة لتخزين بيانات كل فقاعة
    bubble_data_list = []
    
    # 3. رسم الأعمدة (LTR Layout)
    start_y_content = cursor_y + 10

    option_letters_ltr = ['A', 'B', 'C', 'D']
    
    for col_index in range(NUM_COLUMNS):
        
        # 🔥 التصحيح: حساب إحداثيات العمود بشكل صحيح
        col_start_x = MARGIN + (column_width * col_index) 
        content_start_x = col_start_x + 10 
        
        # 3.1. رسم رؤوس الأعمدة (A, B, C, D) 
        header_y = start_y_content
        
        # مكان بدء الفقاعات (بعد رقم السؤال)
        bubbles_x_start = content_start_x + q_num_label_width
        
        for i, letter in enumerate(option_letters_ltr):
            
            text_width, text_height = get_text_metrics(draw, letter, font_medium)
            
            center_x = bubbles_x_start + (i * (2 * bubble_radius + bubble_x_spacing)) + bubble_radius 
            
            draw.text((center_x - text_width / 2, header_y),
                         letter, fill='black', font=font_medium)
        
        # 3.2. رسم الأسئلة داخل العمود
        current_y = header_y + text_height + 45
        
        # 🔥 التصحيح: ترقيم الأسئلة بشكل صحيح
        start_q = col_index * QUESTIONS_PER_COLUMN + 1
        end_q = min((col_index + 1) * QUESTIONS_PER_COLUMN, num_questions)

        for q_num in range(start_q, end_q + 1):
            
            if current_y + (bubble_radius * 2) > HEIGHT - MARGIN:
                break
            
            # 1. رسم رقم السؤال
            q_num_text = f"{q_num}."
            num_text_width, num_text_height = get_text_metrics(draw, q_num_text, font_small)
            
            num_x = content_start_x
            num_y = current_y + bubble_radius - (num_text_height / 2) 
            
            draw.text((num_x, num_y), q_num_text, fill='black', font=font_small)
            
            # 2. رسم الدوائر (الببلز)
            for i in range(MAX_OPTIONS):
                
                center_x = bubbles_x_start + (i * (2 * bubble_radius + bubble_x_spacing)) + bubble_radius
                center_y = current_y + bubble_radius
                
                bbox_bubble = [
                    center_x - bubble_radius, 
                    center_y - bubble_radius, 
                    center_x + bubble_radius, 
                    center_y + bubble_radius
                ]
                
                draw.ellipse(bbox_bubble, outline='black', width=3) 
                
                # --- 🔥 إضافة ID للفقاعة وتسجيل البيانات 🔥 ---
                option_letter = option_letters_ltr[i]
                # إنشاء ID فريد (رقم السؤال + حرف الخيار)
                bubble_id = f"Q{q_num}-{option_letter}" 
                
                bubble_data_list.append({
                    'id': bubble_id,
                    'question_num': q_num,
                    'option_letter': option_letter,
                    'center_x': int(center_x),
                    'center_y': int(center_y),
                    # يتم تسجيل مربع الإحاطة (bounding box) بحدوده الأربعة لسهولة معالجته بالصور
                    'bbox': [int(b) for b in bbox_bubble] 
                })
                # --------------------------------------------------
                
            current_y += bubble_radius * 2 + 5 
            
        cursor_y = max(cursor_y, current_y)

    # 🔥 إضافة تعليمات التظليل
    instructions_y = cursor_y + 30
    instructions = [
        "تعليمات:",
        "- استخدم قلم رصاص 2B للتظليل",
        "- ظلل الدائرة بالكامل",
        "- لا تضع علامات خارج الدوائر",
        "- تأكد من أن التظليل داكن وكافي"
    ]
    
    for instruction in instructions:
        processed_instruction = fix_arabic_text(instruction)
        text_width, text_height = get_text_metrics(draw, processed_instruction, font_small)
        draw.text((WIDTH - MARGIN - text_width, instructions_y), processed_instruction, fill='black', font=font_small)
        instructions_y += text_height + 10

    # حفظ الصورة
    final_output_filename = output_filename.replace('.png', '_AnswerSheet.png')
    
    successful = True
    try:
        if num_questions > QUESTIONS_PER_COLUMN * NUM_COLUMNS:
            print(f"⚠️ تنبيه: تم تصميم ورقة الإجابة لـ {QUESTIONS_PER_COLUMN * NUM_COLUMNS} سؤال فقط.")
            
        img.save(final_output_filename)
        print(f"✅ تم إنشاء ورقة الإجابة (Bubble Sheet مصححة) بنجاح: {final_output_filename}")
        print(f"📊 توزيع الأسئلة: العمود1: 1-20, العمود2: 21-40, العمود3: 41-60")
        
    except Exception as e:
        print(f"❌ فشل في إخراج ورقة الإجابة: {e}")
        successful = False

    # 🔥 حفظ بيانات الفقاعات في ملف JSON منفصل
    if successful:
        data_output_filename = final_output_filename.replace('.png', '_BubbleData.json')
        try:
            with open(data_output_filename, 'w', encoding='utf-8') as f:
                json.dump(bubble_data_list, f, indent=4, ensure_ascii=False)
            print(f"✅ تم حفظ بيانات الفقاعات (بما في ذلك الـ IDs) في: {data_output_filename}")
            
            # طباعة مثال لأول 5 فقاعات
            print("🔍 مثال على بيانات الفقاعات (أول 5):")
            for item in bubble_data_list[:5]:
                print(f"   -> ID: {item['id']}, Q: {item['question_num']}, Option: {item['option_letter']}, Center: ({item['center_x']}, {item['center_y']}), BBox: {item['bbox']}")
                
        except Exception as e:
            print(f"❌ فشل في حفظ ملف بيانات الفقاعات: {e}")
            successful = False

    return successful

# --- الدالة الرئيسية للتنفيذ ---

def generate_all_exam_sheets():
    """المرور على بيانات الامتحان وإنشاء ملفي صورة (الأسئلة والإجابة) لكل طالب، بالإضافة إلى ملف بيانات الفقاعات."""
    
    exam_group_data = load_exam_data(JSON_FILE)
    
    if not exam_group_data:
        print("لا توجد بيانات امتحان رئيسية لمعالجتها.")
        return

    users = exam_group_data.get('users', [])
    
    if not users:
        print("لا توجد بيانات مستخدمين (طلاب) في ملف JSON لمعالجتها.")
        return

    exam_info = {
        'stage': exam_group_data.get('stage', 'N/A'),
        'subject_name': exam_group_data.get('subject_name', 'N/A'),
        'subject_id': exam_group_data.get('subject_id', 'N/A'),
        'model_type': exam_group_data.get('model_type', 'N/A') 
    }
    
    num_questions_to_print = 0
    if users and users[0].get('exam'):
        num_questions_to_print = len(users[0].get('exam', []))
        
    print(f"🌟 جارٍ إنشاء أوراق الامتحان (الأسئلة والإجابة لـ {num_questions_to_print} سؤال) كصور لـ {len(users)} طالب/طالبة...")

    for user in users:
        user_id = user.get('id')
        user_name = user.get('name')
        
        if not user_id or not user.get('exam') or len(user.get('exam', [])) < 1:
            if user_name:
                print(f"⚠️ تنبيه: تم تخطي الطالب {user_name} - البيانات غير كاملة.")
            continue

        user_model_type = user.get('model_type', exam_info['model_type'])
        
        qrcode_data_dict = {
            "اسم الطالب": user_name,
            "ID الطالب": user_id,
            "معرف المادة": exam_info['subject_id'],
            "عدد الأسئلة": num_questions_to_print,
            "معلومات الامتحان": {
                "المرحلة": exam_info['stage'],
                "اسم المادة": exam_info['subject_name'],
                "نوع النموذج": user_model_type
            }
        }

        qrcode_data = json.dumps(qrcode_data_dict, ensure_ascii=False)

        qrcode_path = os.path.join(OUTPUT_DIR, f"qrcode_{user_id}.png")
        # تم تغيير امتداد الملف الأساسي ليعكس أنه سيتم إنشاء عدة ملفات
        base_filename = os.path.join(OUTPUT_DIR, f"Exam_{exam_info['subject_name']}_{user_model_type}_{user_id}_{user_name}.png").replace(' ', '_')
        
        if generate_qrcode(qrcode_data, qrcode_path):
            try:
                # 1. إنشاء صفحة الأسئلة
                create_student_exam_image(exam_info, user, base_filename, qrcode_path)
                
                # 2. إنشاء صفحة الإجابة (Bubble Sheet المصححة)
                # هذه الدالة ستقوم الآن بحفظ ملف JSON لبيانات الفقاعات
                create_bubble_sheet_image(exam_info, user, base_filename, qrcode_path)
                
            except SystemExit:
                print("🛑 توقف التنفيذ بسبب خطأ في الخط.")
                return
            except Exception as e:
                print(f"🛑 خطأ غير متوقع أثناء إنشاء الصورة للطالب {user_name}: {e}")
            finally:
                if os.path.exists(qrcode_path):
                    os.remove(qrcode_path)
                    
        else:
            print(f"❌ تم تخطي الطالب {user_name} بسبب فشل إنشاء QR Code.")

# --- تشغيل البرنامج ---
if __name__ == '__main__':
    if not os.path.exists(FONT_PATH):
        print(f"🛑 خطأ فادح: ملف الخط '{FONT_PATH}' غير موجود.")
    else:
        generate_all_exam_sheets()