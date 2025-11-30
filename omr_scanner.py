import cv2
import numpy as np
import json
import os

# --- 1. الدوال المساعدة (Helper Functions) ---

def get_filled_ratio(bubble_roi):
    """حساب نسبة البكسلات المظللة داخل دائرة الإجابة."""
    # نستخدم عتبة ثابتة لتمييز التظليل الغامق
    # يجب أن تكون المنطقة بيضاء (255) والتظليل أسود (0)
    # cv2.THRESH_BINARY_INV يجعل التظليل (الغامق) هو البكسلات التي يتم عدّها
    _, thresh = cv2.threshold(bubble_roi, 100, 255, cv2.THRESH_BINARY_INV)
    filled_pixels = cv2.countNonZero(thresh)
    total_pixels = bubble_roi.shape[0] * bubble_roi.shape[1]
    
    # نسبة التعبئة
    if total_pixels > 0:
        return filled_pixels / float(total_pixels)
    return 0.0

def load_bubble_data(json_path):
    """تحميل بيانات الفقاعات من ملف JSON وتجميعها حسب رقم السؤال."""
    try:
        # 🔑 تم استخدام مسار الملف الذي تم رفعه من قبل المستخدم
        with open(json_path, 'r', encoding='utf-8') as f:
            all_bubbles = json.load(f)
    except FileNotFoundError:
        print(f"❌ خطأ: لم يتم العثور على ملف JSON في المسار: {json_path}")
        return None
    except json.JSONDecodeError:
        print(f"❌ خطأ: فشل في فك ترميز JSON من الملف: {json_path}")
        return None

    questions_data = {}
    for bubble in all_bubbles:
        q_num = bubble.get('question_num')
        if q_num is not None:
            # تجميع الفقاعات حسب رقم السؤال
            if q_num not in questions_data:
                questions_data[q_num] = []
            questions_data[q_num].append(bubble)
            
    # فرز الخيارات داخل كل سؤال حسب حرف الخيار (A, B, C, D) لضمان الترتيب الصحيح
    for q_num in questions_data:
        questions_data[q_num].sort(key=lambda x: x.get('option_letter', 'Z')) # 'Z' لضمان أن الخيارات بدون حرف تذهب إلى النهاية
        
    return questions_data


# --- 2. الإعدادات والمعلمات (Configuration) ---

IMAGE_PATH = 'text_exam.png'
# 🔑 مسار ملف JSON المُحمَّل
JSON_DATA_PATH = 'Exam_حاسوب_Group_1_زيد_حسين_محمد_AnswerSheet_BubbleData.json'

TOTAL_QUESTIONS = 60 
OPTIONS_PER_QUESTION = 4

# الحد الأدنى لنسبة التظليل لاعتبار الفقاعة مُظلّلة
MIN_MARK_FILL_RATIO = 0.45


# --- 3. الدالة الرئيسية (Main Function) ---

def process_omr_sheet(image_path, json_data_path):
    # 1. تحميل الصورة والتحقق من وجودها
    image = cv2.imread(image_path)
    if image is None:
        print(f"❌ خطأ: تعذر تحميل الصورة من المسار {image_path}. يرجى التأكد من وجود ملف 'text_exam.png' في نفس المجلد.")
        return None
    
    print(f"✅ تم تحميل الصورة بنجاح: {image_path}")

    # 2. تحميل بيانات الفقاعات من JSON
    questions_data = load_bubble_data(json_data_path)
    if questions_data is None:
        return None
        
    global TOTAL_QUESTIONS
    TOTAL_QUESTIONS = len(questions_data)
    print(f"✅ تم تحميل بيانات {TOTAL_QUESTIONS} سؤال من ملف JSON.")

    # 3. معالجة الصورة
    output_image = image.copy()
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # ملاحظة: لم نعد نحتاج إلى Blur، Canny، أو Contours، حيث نعتمد على الإحداثيات مباشرة.

    final_answers = []
    
    # 4. معالجة الإجابات سؤالاً بسؤال بناءً على إحداثيات JSON
    # فرز أرقام الأسئلة لضمان معالجتها بالتسلسل الصحيح (1، 2، 3، ...)
    sorted_q_nums = sorted(questions_data.keys())
    
    for q_num in sorted_q_nums:
        
        question_options = questions_data[q_num]
        
        # التأكد من وجود 4 خيارات لكل سؤال
        if len(question_options) != OPTIONS_PER_QUESTION:
            print(f"⚠️ تنبيه: السؤال رقم {q_num} يحتوي على {len(question_options)} خياراً بدلاً من {OPTIONS_PER_QUESTION}. سيتم تخطيه.")
            continue
            
        marked_bubble_id = None
        marked_option_letter = "Unanswered"
        max_ratio = 0.0
        
        # حلقة لاكتشاف الإجابة المظللة من بين الخيارات الأربعة
        for bubble_data in question_options:
            
            # استخراج إحداثيات المستطيل (x_min, y_min, x_max, y_max)
            try:
                x_min, y_min, x_max, y_max = bubble_data['bbox']
            except (KeyError, ValueError):
                print(f"❌ خطأ في بيانات bbox للفقاعة {bubble_data.get('id', 'غير معروف')}.")
                continue
            
            # التأكد من عدم خروج الإحداثيات عن حدود الصورة
            h, w = gray.shape
            x_min = max(0, x_min)
            y_min = max(0, y_min)
            x_max = min(w, x_max)
            y_max = min(h, y_max)
            
            # استخراج منطقة الاهتمام (ROI) للدائرة من الصورة الرمادية
            bubble_roi = gray[y_min:y_max, x_min:x_max]
            
            if bubble_roi.size == 0 or (x_max - x_min) <= 0 or (y_max - y_min) <= 0:
                continue # تخطي إذا كانت المنطقة غير صالحة

            fill_ratio = get_filled_ratio(bubble_roi)
            
            # إذا كان التظليل هو الأقصى، يتم اعتباره الإجابة المحتملة
            if fill_ratio > max_ratio:
                max_ratio = fill_ratio
                marked_bubble_id = bubble_data['id']
                marked_option_letter = bubble_data['option_letter']
                
        
        # 5. تحديد الإجابة النهائية
        is_marked = (max_ratio >= MIN_MARK_FILL_RATIO)
        
        current_answer = {
            "id": q_num, 
            "answer": marked_option_letter if is_marked else "Unanswered",
            "bubble_id": marked_bubble_id if is_marked else None # إضافة الـ ID الخاص بالفقاعة المظللة
        }
        final_answers.append(current_answer)
        
        # 6. رسم مستطيل أخضر حول الإجابة المكتشفة (للتصور)
        if is_marked and marked_bubble_id:
            # البحث عن بيانات الفقاعة المظللة لغرض الرسم
            marked_bubble_data = next((b for b in question_options if b['id'] == marked_bubble_id), None)
            if marked_bubble_data:
                x_min, y_min, x_max, y_max = marked_bubble_data['bbox']
                # رسم مستطيل أخضر (سمك 3) على الإجابة المكتشفة
                cv2.rectangle(output_image, (x_min, y_min), (x_max, y_max), (0, 255, 0), 3)


    # 7. إخراج البيانات JSON بالبنية المطلوبة
    
    output_data = {
      "data": {
        "stage": "stage 1",
        "subject_id": 1,
        "subject_name": "حاسوب",
        "exam_info": { "id": 1 },
        "n_of_Q": TOTAL_QUESTIONS,
        "model_type": "Group A",
        "number_of_groups": "4",
        "number_of_questions": TOTAL_QUESTIONS,
        "users": [
          {
            "id": 1,
            "name": "زيد حسين محمد",
            "email": "superadmin@example.com",
            "user_info": { "deb": "ddeee" },
            "exam": [
              {
                "id": 1,
                "answer": final_answers
              }
            ]
          }
        ]
      }
    }

    # حفظ ملف JSON
    output_json_path = 'student_answers_structured_json_based.json'
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)
        
    print(f"\n✅ تم حفظ الإجابات في {output_json_path} بنجاح لـ {len(final_answers)} سؤال.")
    
    # حفظ وعرض الصورة المعالجة
    output_image_path = 'output_answers_structured_json_based_image.png'
    cv2.imwrite(output_image_path, output_image)
    print(f"✅ تم حفظ الصورة المعالجة في: {output_image_path}")

    # عرض الصورة المعالجة باستخدام OpenCV
    if os.path.exists(image_path):
        cv2.imshow("OMR Answers Detected (JSON Based)", output_image)
        cv2.waitKey(0)
        cv2.destroyAllWindows()


# --- تنفيذ الكود ---
if __name__ == "__main__":
    # تمرير مسار الصورة ومسار ملف JSON إلى الدالة الرئيسية
    process_omr_sheet(IMAGE_PATH, JSON_DATA_PATH)