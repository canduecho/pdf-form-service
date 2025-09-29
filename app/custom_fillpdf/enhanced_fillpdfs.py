import fitz
import math
import pdfrw
from pdf2image import convert_from_path # Needs conda install -c conda-forge poppler
from PIL import Image
from collections import OrderedDict

from .utils.field_format import is_text_field_multiline, make_read_only
def _safe_int_convert(value):
    """
    安全地将值转换为整数
    """
    if value is None:
        return None
    try:
        if isinstance(value, int):
            return value
        elif hasattr(value, 'to_unicode'):
            value_str = value.to_unicode()
            if value_str.isdigit():
                return _safe_int_convert(value_str)
        elif isinstance(value, str) and value.isdigit():
            return _safe_int_convert(value)
        return None
    except:
        return None


def _get_acroform_fields(pdf):
    """
    Enhanced: 从PDF的AcroForm结构中提取特殊字段（如子字段）
    这些字段可能不出现在页面注释中，但存在于AcroForm字段树中
    """
    acroform_fields = {}
    
    try:
        # 检查是否有AcroForm
        if not pdf.Root or not pdf.Root.AcroForm or not pdf.Root.AcroForm.Fields:
            return acroform_fields
        
        # 遍历AcroForm字段树，使用改进的递归函数
        for field in pdf.Root.AcroForm.Fields:
            _extract_field_recursive_improved(field, acroform_fields)
            
    except Exception as e:
        # 静默处理异常，不影响原有功能
        pass
    
    return acroform_fields

def _extract_field_recursive(field_obj, result_dict, parent_name=""):
    """
    递归提取字段，包括父子字段结构
    """
    if not field_obj:
        return
    
    try:
        # 获取字段名
        field_name = None
        if '/T' in field_obj:
            field_name = field_obj['/T']
            if hasattr(field_name, 'to_unicode'):
                field_name = field_name.to_unicode()
            elif isinstance(field_name, str):
                field_name = field_name.strip('()')
            else:
                # 处理其他类型的字段名
                field_name = str(field_name).strip('()')
        
        # 构建完整字段名
        full_name = f"{parent_name}.{field_name}" if parent_name and field_name else (field_name or parent_name)
        
        # 获取字段值
        field_value = ""
        if '/V' in field_obj:
            try:
                value = field_obj['/V']
                if hasattr(value, 'decode'):
                    field_value = value.decode('utf-8', errors='ignore')
                elif isinstance(value, str):
                    field_value = value.strip('()')
                else:
                    field_value = str(value).strip('()')
            except:
                pass
        
        # 如果有字段名且不在结果中，添加它，同时记录字段类型信息
        if field_name and field_name not in result_dict:
            result_dict[field_name] = {
                'value': field_value,
                'type': field_obj.get('/FT') if '/FT' in field_obj else None,
                'subtype': field_obj.get('/Subtype') if '/Subtype' in field_obj else None,
                'has_options': '/Opt' in field_obj,
                'has_kids': '/Kids' in field_obj and field_obj['/Kids'],
                'options': [],
                'flags': _safe_int_convert(field_obj.get('/Ff')) if '/Ff' in field_obj and field_obj['/Ff'] else None,  # 添加标志位信息并转换为int
                'max_length': _safe_int_convert(field_obj.get('/MaxLen')) if '/MaxLen' in field_obj and field_obj['/MaxLen'] else None  # 添加最大长度
            }
            
            # 提取选项（用于下拉框、列表框）
            if '/Opt' in field_obj and field_obj['/Opt']:
                try:
                    options = field_obj['/Opt']
                    option_list = []
                    for opt in options:
                        if hasattr(opt, 'to_unicode'):
                            option_list.append(opt.to_unicode())
                        elif isinstance(opt, str):
                            option_list.append(opt.strip('()'))
                        else:
                            opt_str = str(opt).strip('()')
                            option_list.append(opt_str)
                    result_dict[field_name]['options'] = option_list
                except Exception as e:
                    # 静默处理选项提取错误
                    pass
            else:
                # 对于Radio字段，尝试从子字段的外观状态中提取选项
                field_type = field_obj.get('/FT')
                flags = field_obj.get('/Ff')
                if field_type == '/Btn' and flags:
                    try:
                        # 安全转换flags为整数
                        flags_int = 0
                        try:
                            if isinstance(flags, int):
                                flags_int = flags
                            elif hasattr(flags, 'to_unicode'):
                                flags_str = flags.to_unicode()
                                if flags_str.isdigit():
                                    flags_int = _safe_int_convert(flags_str)
                            elif isinstance(flags, str) and flags.isdigit():
                                flags_int = _safe_int_convert(flags)
                        except:
                            flags_int = 0
                        is_radio = bool(flags_int & 32768)
                        
                        if is_radio and '/Kids' in field_obj and field_obj['/Kids']:
                            # 从子字段的外观状态中提取选项
                            appearance_options = []
                            for kid in field_obj['/Kids']:
                                if '/AP' in kid and '/N' in kid['/AP']:
                                    ap_n = kid['/AP']['/N']
                                    if isinstance(ap_n, dict):
                                        for state_name in ap_n.keys():
                                            state_str = str(state_name).strip('/')
                                            if state_str != 'Off' and state_str not in appearance_options:
                                                appearance_options.append(state_str)
                            
                            if appearance_options:
                                # 排序选项以确保一致性
                                appearance_options.sort()
                                result_dict[field_name]['options'] = appearance_options
                                result_dict[field_name]['has_options'] = True
                    except:
                        pass
        
        # 处理子字段
        if '/Kids' in field_obj and field_obj['/Kids']:
            kids = field_obj['/Kids']
            for kid in kids:
                # 直接使用kid对象
                kid_obj = kid
                # 对于子字段，如果父字段没有值，尝试从子字段获取值
                if field_name and not field_value and '/V' in kid_obj:
                    try:
                        kid_value = kid_obj['/V']
                        if hasattr(kid_value, 'to_unicode'):
                            kid_value = kid_value.to_unicode()
                        elif hasattr(kid_value, 'decode'):
                            kid_value = kid_value.decode('utf-8', errors='ignore')
                        elif isinstance(kid_value, str):
                            kid_value = kid_value.strip('()')
                        else:
                            kid_value = str(kid_value).strip('()')
                        
                        # 更新值，保持其他信息不变
                        if field_name in result_dict:
                            result_dict[field_name]['value'] = kid_value
                        else:
                                                    result_dict[field_name] = {
                            'value': kid_value,
                            'type': field_obj.get('/FT') if '/FT' in field_obj else None,
                            'subtype': field_obj.get('/Subtype') if '/Subtype' in field_obj else None,
                            'has_options': '/Opt' in field_obj,
                            'has_kids': True,
                            'options': [],
                            'flags': _safe_int_convert(field_obj.get('/Ff')) if '/Ff' in field_obj and field_obj['/Ff'] else None,
                            'max_length': _safe_int_convert(field_obj.get('/MaxLen')) if '/MaxLen' in field_obj and field_obj['/MaxLen'] else None
                        }
                        break  # 找到值后停止搜索其他子字段
                    except:
                        pass
                
                # 递归处理子字段（无论是否找到值都要继续递归）
                _extract_field_recursive(kid_obj, result_dict, full_name if full_name else "")
                
    except Exception as e:
        # 静默处理单个字段的异常
        pass

def _fill_acroform_fields(template_pdf, data_dict):
    """
    Enhanced: 直接在AcroForm字段树中填充特殊字段（如子字段）
    这些字段可能无法通过页面注释处理
    """
    if not template_pdf.Root or not template_pdf.Root.AcroForm or not template_pdf.Root.AcroForm.Fields:
        return
    
    # 遍历AcroForm字段树
    for field in template_pdf.Root.AcroForm.Fields:
        # 直接使用field对象
        _fill_field_recursive(field, data_dict)

def _fill_field_recursive(field_obj, data_dict, parent_name=""):
    """
    递归填充字段，包括父子字段结构
    """
    if not field_obj:
        return
    
    try:
        # 获取字段名
        field_name = None
        if '/T' in field_obj:
            field_name = field_obj['/T']
            if hasattr(field_name, 'to_unicode'):
                field_name = field_name.to_unicode()
            elif isinstance(field_name, str):
                field_name = field_name.strip('()')
        
        # 如果字段名在data_dict中，尝试填充
        if field_name and field_name in data_dict:
            field_value = data_dict[field_name]
            
            # 检查字段类型
            field_type = field_obj.get('/FT') if '/FT' in field_obj else None
            
            # 根据字段类型进行不同的处理
            if field_type == '/Tx' or field_type is None:
                # 文本字段或父字段
                try:
                    field_obj[pdfrw.PdfName.V] = pdfrw.PdfString.encode(str(field_value))
                except:
                    try:
                        field_obj[pdfrw.PdfName.V] = str(field_value)
                    except:
                        pass  # 父字段可能不允许直接设置值
                
                # 如果有子字段，也设置子字段的值
                if '/Kids' in field_obj and field_obj['/Kids']:
                    for kid in field_obj['/Kids']:
                        try:
                            kid[pdfrw.PdfName.V] = pdfrw.PdfString.encode(str(field_value))
                        except:
                            kid[pdfrw.PdfName.V] = str(field_value)
                            
            elif field_type == '/Btn':
                # 按钮字段（复选框、单选按钮）
                try:
                    # 检查是否为radio字段（检查flags而不是选项）
                    flags = field_obj.get('/Ff')
                    is_radio = False
                    if flags:
                        try:
                            # 安全转换PdfObject为整数
                            flags_int = 0
                            try:
                                if hasattr(flags, 'to_unicode'):
                                    flags_str = flags.to_unicode()
                                    if flags_str.isdigit():
                                        flags_int = _safe_int_convert(flags_str)
                                elif isinstance(flags, str) and flags.isdigit():
                                    flags_int = _safe_int_convert(flags)
                                elif isinstance(flags, int):
                                    flags_int = flags
                            except:
                                flags_int = 0
                            is_radio = bool(flags_int & 32768)
                        except:
                            is_radio = False
                    
                    if is_radio or ('/Opt' in field_obj and field_obj['/Opt']):
                        # Radio字段：根据是否有选项进行不同处理
                        if '/Opt' in field_obj and field_obj['/Opt']:
                            # 有选项的radio字段：根据值索引选择对应选项
                            try:
                                value_index = _safe_int_convert(field_value)
                                if value_index is None:
                                    value_index = 0
                                options = field_obj['/Opt']
                                
                                # 设置父字段值为选中的选项
                                if 0 <= value_index < len(options):
                                    selected_option = options[value_index]
                                    if hasattr(selected_option, 'to_unicode'):
                                        option_text = selected_option.to_unicode()
                                    else:
                                        option_text = str(selected_option).strip('()')
                                    field_obj[pdfrw.PdfName.V] = pdfrw.PdfString.encode(str(value_index))
                                
                                # 处理radio按钮组的子字段
                                if '/Kids' in field_obj and field_obj['/Kids']:
                                    for idx, kid in enumerate(field_obj['/Kids']):
                                        try:
                                            if idx == value_index:
                                                # 选中这个radio按钮
                                                kid[pdfrw.PdfName.V] = pdfrw.PdfString.encode(str(value_index))
                                                kid[pdfrw.PdfName.AS] = pdfrw.PdfString.encode(str(value_index))
                                            else:
                                                # 取消选择其他radio按钮
                                                kid[pdfrw.PdfName.V] = pdfrw.PdfName.Off
                                                kid[pdfrw.PdfName.AS] = pdfrw.PdfName.Off
                                        except:
                                            pass
                            except (ValueError, IndexError):
                                # 如果值不是有效索引，设置为Off
                                field_obj[pdfrw.PdfName.V] = pdfrw.PdfName.Off
                                field_obj[pdfrw.PdfName.AS] = pdfrw.PdfName.Off
                        else:
                            # 没有选项的radio字段：直接设置值
                            try:
                                # 设置父字段值
                                field_obj[pdfrw.PdfName.V] = pdfrw.PdfString.encode(str(field_value))
                                field_obj[pdfrw.PdfName.AS] = pdfrw.PdfString.encode(str(field_value))
                                
                                # 处理子字段：所有子字段都设置为相同值
                                if '/Kids' in field_obj and field_obj['/Kids']:
                                    for kid in field_obj['/Kids']:
                                        try:
                                            kid[pdfrw.PdfName.V] = pdfrw.PdfString.encode(str(field_value))
                                            kid[pdfrw.PdfName.AS] = pdfrw.PdfString.encode(str(field_value))
                                        except:
                                            pass
                            except:
                                # 如果设置失败，尝试设置为Off
                                field_obj[pdfrw.PdfName.V] = pdfrw.PdfName.Off
                                field_obj[pdfrw.PdfName.AS] = pdfrw.PdfName.Off
                    else:
                        # Checkbox字段：简单的on/off处理
                        if str(field_value).lower() in ['1', 'true', 'yes', 'on', 'checked']:
                            field_obj[pdfrw.PdfName.V] = pdfrw.PdfString.encode('Yes')
                            field_obj[pdfrw.PdfName.AS] = pdfrw.PdfString.encode('Yes')
                        else:
                            field_obj[pdfrw.PdfName.V] = pdfrw.PdfName.Off
                            field_obj[pdfrw.PdfName.AS] = pdfrw.PdfName.Off
                        
                        # 处理checkbox的子字段
                        if '/Kids' in field_obj and field_obj['/Kids']:
                            for kid in field_obj['/Kids']:
                                try:
                                    if str(field_value).lower() in ['1', 'true', 'yes', 'on', 'checked']:
                                        kid[pdfrw.PdfName.V] = pdfrw.PdfString.encode('Yes')
                                        kid[pdfrw.PdfName.AS] = pdfrw.PdfString.encode('Yes')
                                    else:
                                        kid[pdfrw.PdfName.V] = pdfrw.PdfName.Off
                                        kid[pdfrw.PdfName.AS] = pdfrw.PdfName.Off
                                except:
                                    pass
                except:
                    pass
                    
            elif field_type == '/Ch':
                # 选择字段（下拉框、列表框）
                try:
                    field_obj[pdfrw.PdfName.V] = pdfrw.PdfString.encode(str(field_value))
                except:
                    field_obj[pdfrw.PdfName.V] = str(field_value)
                    
            elif field_type == '/Sig':
                # 签名字段（通常不需要填充值）
                pass
        
        # 递归处理子字段
        if '/Kids' in field_obj and field_obj['/Kids']:
            for kid in field_obj['/Kids']:
                # 直接使用kid对象
                full_name = f"{parent_name}.{field_name}" if parent_name and field_name else (field_name or parent_name)
                _fill_field_recursive(kid, data_dict, full_name)
                
    except Exception as e:
        # 静默处理单个字段的异常
        pass

ANNOT_KEY = '/Annots'               # key for all annotations within a page
ANNOT_FIELD_KEY = '/T'              # Name of field. i.e. given ID of field
ANNOT_FORM_type = '/FT'             # Form type (e.g. text/button)
ANNOT_FORM_button = '/Btn'          # ID for buttons, i.e. a checkbox
ANNOT_FORM_text = '/Tx'             # ID for textbox
ANNOT_FORM_options = '/Opt'
ANNOT_FORM_combo = '/Ch'
SUBTYPE_KEY = '/Subtype'
WIDGET_SUBTYPE_KEY = '/Widget'
ANNOT_FIELD_PARENT_KEY = '/Parent'  # Parent key for older pdf versions
ANNOT_FIELD_KIDS_KEY = '/Kids'      # Kids key for older pdf versions
ANNOT_VAL_KEY = '/V'
ANNOT_RECT_KEY = '/Rect'

def get_form_fields(input_pdf_path, sort=False, page_number=None):
    """
    Retrieves the form fields from a pdf to then be stored as a dictionary and
    passed to the write_fillable_pdf() function. Uses pdfrw.
    Parameters
    ---------
    input_pdf_path: str
        Path to the pdf you want the fields from.
    Returns
    ---------
    A dictionary of form fields and their filled values.
    """
    data_dict = {}

    pdf = pdfrw.PdfReader(input_pdf_path)
    count = 1
    if page_number is not None:
        if type(page_number) == int:
            if page_number > 0:
                if page_number <= len(pdf.pages):
                    pass
                else:
                    raise ValueError(f"page_number must be inbetween 1 & {len(pdf.pages)}")
            else:
                raise ValueError(f"page_number must be inbetween 1 & {len(pdf.pages)}")
        else:
            raise ValueError(f"page_number must be an int")
    for page in pdf.pages:
        if page_number is not None:
            if count != page_number:
                count += 1
                continue
            else:
                pr_safe_int_convert(f"Values From Page {page_number}")
        annotations = page[ANNOT_KEY]
        if annotations:
            for annotation in annotations:
                if annotation[SUBTYPE_KEY] == WIDGET_SUBTYPE_KEY:
                    if annotation[ANNOT_FIELD_KEY]:
                        key = annotation[ANNOT_FIELD_KEY][1:-1]
                        # 只有当字段不存在或当前值为空时，才设置新值
                        if key not in data_dict or not data_dict[key]:
                            data_dict[key] = ''
                        if annotation[ANNOT_VAL_KEY]:
                            value = annotation[ANNOT_VAL_KEY]
                            data_dict[key] = annotation[ANNOT_VAL_KEY]
                            try:
                                if type(annotation[ANNOT_VAL_KEY]) == pdfrw.objects.pdfstring.PdfString:
                                    data_dict[key] = pdfrw.objects.PdfString.decode(annotation[ANNOT_VAL_KEY])
                                elif type(annotation[ANNOT_VAL_KEY]) == pdfrw.objects.pdfname.BasePdfName:
                                    if '/' in annotation[ANNOT_VAL_KEY]:
                                        data_dict[key] = annotation[ANNOT_VAL_KEY][1:]
                            except:
                                pass
                    elif annotation['/AP']:
                        if not annotation['/T']:
                            annotation = annotation['/Parent']
                        key = annotation['/T'].to_unicode()
                        data_dict[key] = annotation[ANNOT_VAL_KEY]
                        try:
                            if type(annotation[ANNOT_VAL_KEY]) == pdfrw.objects.pdfstring.PdfString:
                                data_dict[key] = pdfrw.objects.PdfString.decode(annotation[ANNOT_VAL_KEY])
                            elif type(annotation[ANNOT_VAL_KEY]) == pdfrw.objects.pdfname.BasePdfName:
                                if '/' in annotation[ANNOT_VAL_KEY]:
                                    data_dict[key] = annotation[ANNOT_VAL_KEY][1:]
                        except:
                            pass
        if count == page_number:
            break
    
    # Enhanced: 添加对特殊字段结构的检测（如子字段）
    enhanced_data_dict = {}
    try:
        acroform_fields = _get_acroform_fields(pdf)
        # 合并AcroForm信息和原始fillpdf值
        for field_name, field_info in acroform_fields.items():
            enhanced_data_dict[field_name] = field_info
            
        # 对于原始方法找到的字段，智能合并值
        for field_name, field_value in data_dict.items():
            if field_name in enhanced_data_dict:
                # 如果AcroForm有这个字段，需要智能选择值
                acroform_value = enhanced_data_dict[field_name]['value']
                has_kids = enhanced_data_dict[field_name].get('has_kids', False)
                
                # 对于有子字段的父字段，优先使用AcroForm提取的值（可能从子字段获取）
                # 对于普通字段，优先使用原始fillpdf的值（更准确）
                if has_kids and acroform_value:
                    # 保持AcroForm提取的子字段值
                    pass
                else:
                    # 使用原始fillpdf的值
                    enhanced_data_dict[field_name]['value'] = field_value
            else:
                # 如果AcroForm没有这个字段，创建基本信息
                enhanced_data_dict[field_name] = {
                    'value': field_value,
                    'type': '/Tx',  # 默认为文本字段
                    'subtype': None,
                    'has_options': False,
                    'has_kids': False,
                    'options': [],
                    'flags': None,
                    'max_length': None
                }
        
        # 使用增强的数据字典
        data_dict = enhanced_data_dict
        
    except Exception as e:
        # 如果AcroForm检测失败，保持原有格式但转换为新结构
        enhanced_data_dict = {}
        for field_name, field_value in data_dict.items():
            enhanced_data_dict[field_name] = {
                'value': field_value,
                'type': '/Tx',
                'subtype': None,
                'has_options': False,
                'has_kids': False,
                'options': [],
                'flags': None,
                'max_length': None
            }
        data_dict = enhanced_data_dict
    
    # 转换回原始格式以保持兼容性，但保留增强信息供后续使用
    result_dict = {}
    enhanced_info = {}  # 存储增强信息
    
    for field_name, field_info in data_dict.items():
        if isinstance(field_info, dict):
            result_dict[field_name] = field_info['value']
            enhanced_info[field_name] = field_info  # 保存完整信息
        else:
            result_dict[field_name] = field_info
    
    # 将增强信息附加到结果中（用于后续处理）
    result_dict['_enhanced_info'] = enhanced_info
    
    if sort == True:
        enhanced_info = result_dict.pop('_enhanced_info', {})
        sorted_dict = dict(sorted(result_dict.items()))
        sorted_dict['_enhanced_info'] = enhanced_info
        return sorted_dict
    else:
        return result_dict


def print_form_fields(input_pdf_path, sort=False, page_number=None):
    """
    Retrieves the form fields from get_form_fields(), then pretty prints
    the data_dict. Uses pdfrw.
    Parameters
    ---------
    input_pdf_path: str
        Path to the pdf you want the fields from.
    Returns
    ---------
    """
    data_dict = get_form_fields(input_pdf_path, sort, page_number)
    print("{" + ",\n".join("{!r}: {!r}".format(k, v) for k, v in data_dict.items()) + "}")


def flatten_pdf(input_pdf_path, output_pdf_path, as_images=False):
    """
    Flattens the pdf so each annotation becomes uneditable. This function provides
    two ways to do so, either with the pdfrw function annotation.update(pdfrw.PdfDict(Ff=1))
    or converting the pages to images then reinserting.
    Parameters
    ---------
    input_pdf_path: str
        Path to the pdf you want to flatten.
    output_pdf_path: str
        Path of the new pdf that is generated.
    as_images: bool
        Default is False meaning it will update each individual annotation and set
        it to False. True means it will convert to images and then reinsert into the
        pdf
    Returns
    ---------
    """
    if as_images == True:
        images = convert_from_path(input_pdf_path) 
        im1 = images[0]
        images.pop(0)

        pdf1_filename = output_pdf_path

        im1.save(pdf1_filename, "PDF" ,resolution=100.0, save_all=True, append_images=images)
    else:
        ANNOT_KEY = '/Annots'               # key for all annotations within a page

        template_pdf = pdfrw.PdfReader(input_pdf_path)
        for Page in template_pdf.pages:
            if Page[ANNOT_KEY]:
                for annotation in Page[ANNOT_KEY]:
                    annotation.update(pdfrw.PdfDict(Ff=1))
        if template_pdf.Root.AcroForm is not None:
            template_pdf.Root.AcroForm.update(pdfrw.PdfDict(NeedAppearances=pdfrw.PdfObject('true')))
        else:
            print("Warning: Form Not Found")
        pdfrw.PdfWriter().write(output_pdf_path, template_pdf)
        

def convert_dict_values_to_string(dictionary):
    """
    Converts dictionary values to string including arrays and tuples.
    Parameters
    ---------
    dictionary: dict
        Any single level dictionary. Specifically made for the data_dict returned from
        the function get_form_fields() from the fillpdf library
    Returns
    ---------
    res: dict
        The resulting dictionary with only string values.
    """
    list_delim, tuple_delim = '-', '^'
  
    res = dict()
    for sub in dictionary:

        # checking data types
        if isinstance(dictionary[sub], list):
            res[sub] = dictionary[sub]
        elif isinstance(dictionary[sub], tuple):
            res[sub] = tuple_delim.join(list([str(ele) for ele in dictionary[sub]]))
        else:
            res[sub] = str(dictionary[sub])
            
    return res    
    
    
def write_fillable_pdf(input_pdf_path, output_pdf_path, data_dict, flatten=False):
    """
    Writes the dictionary values to the pdf. Currently supports text and buttons.
    Does so by updating each individual annotation with the contents of the dat_dict.
    Parameters
    ---------
    input_pdf_path: str
        Path to the pdf you want to flatten.
    output_pdf_path: str
        Path of the new pdf that is generated.
    data_dict: dict
        The data_dict returned from the function get_form_fields()
    flatten: bool
        Default is False meaning it will stay editable. True means the annotations
        will be uneditable.
    Returns
    ---------
    """
    data_dict = convert_dict_values_to_string(data_dict)

    template_pdf = pdfrw.PdfReader(input_pdf_path)
    for Page in template_pdf.pages:
        if Page[ANNOT_KEY]:
            for annotation in Page[ANNOT_KEY]:
                target = annotation if annotation[ANNOT_FIELD_KEY] else annotation[ANNOT_FIELD_PARENT_KEY]
                if annotation[ANNOT_FORM_type] == None:
                    pass
                if target and annotation[SUBTYPE_KEY] == WIDGET_SUBTYPE_KEY:
                    key = target[ANNOT_FIELD_KEY][1:-1] # Remove parentheses
                    target_aux = target
                    while target_aux['/Parent']:
                        key = target['/Parent'][ANNOT_FIELD_KEY][1:-1] + '.' + key
                        target_aux = target_aux['/Parent']
                    if key in data_dict.keys():
                        if target[ANNOT_FORM_type] == ANNOT_FORM_button:
                            # button field i.e. a radiobuttons
                            if not annotation['/T']:
                                if annotation['/AP']:
                                    keys = annotation['/AP']['/N'].keys()
                                    if keys[0]:
                                        if keys[0][0] == '/':
                                            keys[0] = str(keys[0][1:])
                                    list_delim, tuple_delim = '-', '^'
                                    res = dict()
                                    for sub in data_dict:
                                        if isinstance(data_dict[sub], list):
                                            res[sub] = list_delim.join([str(ele) for ele in data_dict[sub]]) 
                                        else:
                                            res[sub] = str(data_dict[sub])
                                    temp_dict = res
                                    annotation = annotation['/Parent']
                                    options = []
                                    for each in annotation['/Kids']:
                                        keys2 = each['/AP']['/N'].keys()
                                        if '/Off' in keys2:
                                            keys2.remove('/Off')
                                        if ['/Off'] in keys:
                                            keys2.remove('/Off')
                                        export = keys2[0]
                                        if '/' in export:
                                            options.append(export[1:])
                                        else:
                                            options.append(export)
                                        if f'/{data_dict[key]}' == export:
                                            val_str = pdfrw.objects.pdfname.BasePdfName(f'/{data_dict[key]}')
                                        else:
                                            val_str = pdfrw.objects.pdfname.BasePdfName(f'/Off')
                                        if set(keys).intersection(set(temp_dict.values())):
                                            each.update(pdfrw.PdfDict(AS=val_str))
                                    if data_dict[key] not in options:
                                        if data_dict[key] != "None"  and data_dict[key] != "":
                                            raise KeyError(f"{data_dict[key]} Not An Option, Options are {options}")
                                    else:
                                        if set(keys).intersection(set(temp_dict.values())):
                                            annotation.update(pdfrw.PdfDict(V=pdfrw.objects.pdfname.BasePdfName(f'/{data_dict[key]}')))
                            else:
                                # button field i.e. a checkbox
                                target.update( pdfrw.PdfDict( V=pdfrw.PdfName(data_dict[key]) , AS=pdfrw.PdfName(data_dict[key]) ))
                                if target[ANNOT_FIELD_KIDS_KEY]:
                                    target[ANNOT_FIELD_KIDS_KEY][0].update( pdfrw.PdfDict( V=pdfrw.PdfName(data_dict[key]) , AS=pdfrw.PdfName(data_dict[key]) ))
                        elif target[ANNOT_FORM_type] == ANNOT_FORM_combo:
                            # Drop Down Combo Box
                            export = None
                            options = annotation[ANNOT_FORM_options]
                            if len(options) > 0:
                                if type(options[0]) == pdfrw.objects.pdfarray.PdfArray:
                                    options = list(options)
                                    options = [pdfrw.objects.pdfstring.PdfString.decode(x[0]) for x in options]
                                if type(options[0]) == pdfrw.objects.pdfstring.PdfString:
                                    options = [pdfrw.objects.pdfstring.PdfString.decode(x) for x in options]
                            if type(data_dict[key]) == list:
                                export = []
                                for each in options:
                                    if each in data_dict[key]:
                                        export.append(pdfrw.objects.pdfstring.PdfString.encode(each))
                                if export is None:
                                    if data_dict[key] != "None"  and data_dict[key] != "":
                                        raise KeyError(f"{data_dict[key]} Not An Option For {annotation[ANNOT_FIELD_KEY]}, Options are {options}")
                                pdfstr = pdfrw.objects.pdfarray.PdfArray(export)
                            else:
                                for each in options:
                                    if each == data_dict[key]:
                                        export = each
                                if export is None:
                                    if data_dict[key] != "None" and data_dict[key] != "":
                                        raise KeyError(f"{data_dict[key]} Not An Option For {annotation[ANNOT_FIELD_KEY]}, Options are {options}")
                                pdfstr = pdfrw.objects.pdfstring.PdfString.encode(data_dict[key])
                            annotation.update(pdfrw.PdfDict(V=pdfstr, AS=pdfstr))
                        elif target[ANNOT_FORM_type] == ANNOT_FORM_text:
                            # regular text field
                            target.update( pdfrw.PdfDict( V=data_dict[key], AP=data_dict[key]) )
                            if target[ANNOT_FIELD_KIDS_KEY]:
                                target[ANNOT_FIELD_KIDS_KEY][0].update( pdfrw.PdfDict( V=data_dict[key], AP=data_dict[key]) )
                if flatten == True:
                    annotation.update(pdfrw.PdfDict(Ff=make_read_only(target["/Ff"])))
    
    # Enhanced: 处理AcroForm中未在页面注释中找到的特殊字段
    try:
        _fill_acroform_fields(template_pdf, data_dict)
    except Exception as e:
        # 如果AcroForm填充失败，不影响原有功能
        pass
    
    template_pdf.Root.AcroForm.update(pdfrw.PdfDict(NeedAppearances=pdfrw.PdfObject('true')))
    pdfrw.PdfWriter().write(output_pdf_path, template_pdf)


def rotate_page(deg, input_pdf_path, output_map_path, page_number, **kwargs):
    """
    Rotate a page within the pdf document.
    Parameters
    ---------
    deg: float
        The x coordinate of the top left corner of the text.
    input_pdf_path: str
        Path to the pdf you want the fields from.
    output_map_path: str
        Path of the new pdf that is generated.
    page_number: float
        Number of the page to get the map of.
    kwargs: Dict
        Additional arguments to pass to fitz save method.
    Returns
    ---------
    """
    doc = fitz.open(input_pdf_path)
    page = doc[page_number-1]
    
    page.set_rotation(deg)
        
    doc.save(output_map_path, **kwargs)


def place_radiobutton(field_name, x, y, input_pdf_path, output_map_path, page_number, width=10, height=10, font_size=12, font_name=None, fill_color=(0.8,0.8,0.8), font_color=(0,0,0), **kwargs):
    """
    Place a radio box in the pdf document. Use the get_coordinate_map
    function to help with placement.
    Parameters
    ---------
    field_name: str
        The name you want attatched to the field
    x: float
        The x coordinate of the top left corner of the text.
    y: float
        The y coordinate of the top right corner of the text.
    input_pdf_path: str
        Path to the pdf you want the fields from.
    output_map_path: str
        Path of the new pdf that is generated.
    page_number: float
        Number of the page to get the map of.
    width: float
        The width of the image
    height: float
        The height of the image
    font_size: float
        Size of the text being inserted.
    font_name: str
        The name of the font type you are using.
        https://github.com/t-houssian/fillpdf/blob/main/README.md#fonts
    fill_color: tuple
        The color to use (0,0,0) = white, (1,1,1) = black
    font_color: tuple
        The color to use (0,0,0) = white, (1,1,1) = black
    kwargs: Dict
        Additional arguments to pass to fitz save method.
    Returns
    ---------
    """
    doc = fitz.open(input_pdf_path)
    page = doc[page_number-1]
    
    widget = fitz.Widget()
    widget.rect = fitz.Rect(x, y, x+width, y+height)
    widget.field_type = fitz.PDF_WIDGET_TYPE_RADIOBUTTON
    widget.text_fontsize = 12
    widget.text_color = font_color
    widget.text_font = font_name
    widget.fill_color = fill_color
    widget.field_name = field_name
    
    page.add_widget(widget)
        
    doc.save(output_map_path, **kwargs)


def place_dropdown(field_name, values, x, y, input_pdf_path, output_map_path, page_number, width=10, height=10, font_size=12, font_name=None, fill_color=(0.8,0.8,0.8), font_color=(0,0,0), **kwargs):
    """
    Place a dropdown box widget in the pdf document. Use the get_coordinate_map
    function to help with placement.
    Parameters
    ---------
    field_name: str
        The name you want attatched to the field
    values: tuple
        The values for the dropdown menu. The first value becomes the default.
    x: float
        The x coordinate of the top left corner of the text.
    y: float
        The y coordinate of the top right corner of the text.
    input_pdf_path: str
        Path to the pdf you want the fields from.
    output_map_path: str
        Path of the new pdf that is generated.
    page_number: float
        Number of the page to get the map of.
    width: float
        The width of the image
    height: float
        The height of the image
    font_size: float
        Size of the text being inserted.
    font_name: str
        The name of the font type you are using.
        https://github.com/t-houssian/fillpdf/blob/main/README.md#fonts
    fill_color: tuple
        The color to use (0,0,0) = white, (1,1,1) = black
    font_color: tuple
        The color to use (0,0,0) = white, (1,1,1) = black
    kwargs: Dict
        Additional arguments to pass to fitz save method.
    Returns
    ---------
    """
    doc = fitz.open(input_pdf_path)
    page = doc[page_number-1]
    widget = fitz.Widget()
    widget.field_name = field_name
    widget.field_label = "Drop Down"
    widget.fill_color = fill_color
    widget.text_color = font_color
    widget.field_type = fitz.PDF_WIDGET_TYPE_LISTBOX
    widget.field_flags = fitz.PDF_CH_FIELD_IS_COMMIT_ON_SEL_CHANGE
    widget.choice_values = values
    widget.rect = fitz.Rect(x, y, x+width, y+height)
    widget.text_fontsize = font_size
    widget.field_value = widget.choice_values[-1]
    page.add_widget(widget)
    
    doc.save(output_map_path, **kwargs)


def place_text_box(field_name, prefilled_text, x, y, input_pdf_path, output_map_path, page_number, width=10, height=10, font_size=12, font_name=None, fill_color=(0.8,0.8,0.8), font_color=(0,0,0), **kwargs):
    """
    Place a fillable text box widget in the pdf document. Use the get_coordinate_map
    function to help with placement.
    Parameters
    ---------
    field_name: str
        The name you want attatched to the field
    prefilled_text: str
        The text you want prefilled in this widget
    x: float
        The x coordinate of the top left corner of the text.
    y: float
        The y coordinate of the top right corner of the text.
    input_pdf_path: str
        Path to the pdf you want the fields from.
    output_map_path: str
        Path of the new pdf that is generated.
    page_number: float
        Number of the page to get the map of.
    width: float
        The width of the image
    height: float
        The height of the image
    font_size: float
        Size of the text being inserted.
    font_name: str
        The name of the font type you are using.
        https://github.com/t-houssian/fillpdf/blob/main/README.md#fonts
    fill_color: tuple
        The color to use (0,0,0) = white, (1,1,1) = black
    font_color: tuple
        The color to use (0,0,0) = white, (1,1,1) = black
    kwargs: Dict
        Additional arguments to pass to fitz save method.
    Returns
    ---------
    """
    doc = fitz.open(input_pdf_path)
    page = doc[page_number-1]
    
    widget = fitz.Widget()
    widget.rect = fitz.Rect(x, y, x+width, y+height)
    widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    widget.text_fontsize = 12
    widget.text_font = font_name
    widget.fill_color = fill_color
    widget.text_color = font_color
    widget.field_name = field_name
    widget.field_value = prefilled_text
    widget.field_label = "arbitrary text - e.g. to help filling the field"
    
    page.add_widget(widget)
    field = page.first_widget
    assert field.field_type_string == "Text"
    
    doc.save(output_map_path, **kwargs)


def place_image(file_name, x, y, input_pdf_path, output_map_path, page_number, width=10, height=10, **kwargs):
    """
    Place image on the pdf document. Use the get_coordinate_map
    function to help with placement.
    Parameters
    ---------
    file_name: str
        The path of the file to be placed in the image
    x: float
        The x coordinate of the top left corner of the text.
    y: float
        The y coordinate of the top right corner of the text.
    input_pdf_path: str
        Path to the pdf you want the fields from.
    output_map_path: str
        Path of the new pdf that is generated.
    page_number: float
        Number of the page to get the map of.
    width: float
        The width of the image
    height: float
        The height of the image
    kwargs: Dict
        Additional arguments to pass to fitz save method.
    Returns
    ---------
    """
    doc = fitz.open(input_pdf_path)
    page = doc[page_number-1]
    
    page.insert_image(fitz.Rect(x, y, x+width, y+height), filename=file_name)
    doc.save(output_map_path, **kwargs)


def place_text(text, x, y, input_pdf_path, output_map_path, page_number, font_size=12, font_name="helv", color=None, **kwargs):
    """
    Place Text on the pdf document. Use the get_coordinate_map
    function to help with placement.
    Parameters
    ---------
    text: str
        The string you want to be place in the document
    x: float
        The x coordinate of the bottom left corner of the text.
    y: float
        The y coordinate of the bootom right corner of the text.
    input_pdf_path: str
        Path to the pdf you want the fields from.
    output_map_path: str
        Path of the new pdf that is generated.
    page_number: float
        Number of the page to get the map of.
    font_size: float
        Size of the text being inserted.
    font_name: str
        The name of the font type you are using.
        https://github.com/t-houssian/fillpdf/blob/main/README.md#fonts
    color: tuple
        The color to use (0,0,0) = white, (1,1,1) = black
    kwargs: Dict
        Additional arguments to pass to fitz save method.
    Returns
    ---------
    """
    doc = fitz.open(input_pdf_path)
    page = doc[page_number-1]
    page.insert_text(fitz.Po_safe_int_convert(x, y), str(text), fontname=font_name, color=color, fontsize=font_size)
    doc.save(output_map_path, **kwargs)


def get_coordinate_map(input_pdf_path, output_map_path, page_number=1, **kwargs):
    """
    Creates a map on the pdf page to help in the placement of text, photos,
    and widgets.
    Parameters
    ---------
    input_pdf_path: str
        Path to the pdf you want the fields from.
    output_map_path: str
        Path of the new pdf that is generated.
    page_number: float
        Number of the page to get the map of.
    kwargs: Dict
        Additional arguments to pass to fitz save method.
    Returns
    ---------
    A dictionary of form fields and their filled values.
    """
    doc = fitz.open(input_pdf_path)
    page = doc[page_number-1]
    max_x = page.rect[2]
    max_y = page.rect[3]
        
    for y in range(0, _safe_int_convert(math.ceil(max_y / 50.0)) * 50, 50): # Drop a dot every 20 px x and y
        page.insert_text(fitz.Po_safe_int_convert(0 , y), str(y), fontsize=12, fontname="times-bold", color=(1, 0, 0))
        page.draw_line(fitz.Po_safe_int_convert(0 , y), fitz.Po_safe_int_convert(max_x , y), color=(1, 0, 0))
        
    for x in range(0, _safe_int_convert(math.ceil(max_x / 50.0)) * 50, 50):
        page.insert_text(fitz.Po_safe_int_convert(x , 12), str(x), fontsize=12, fontname="times-bold", color=(1, 0, 0))
        page.draw_line(fitz.Po_safe_int_convert(x , 12), fitz.Po_safe_int_convert(x , max_y), color=(1, 0, 0))
    
    doc.save(output_map_path, **kwargs)

def _extract_field_recursive_improved(field_obj, result_dict, parent_path=""):
    """
    改进的递归提取字段函数，能够处理深层嵌套结构
    """
    if not field_obj:
        return
    
    try:
        # 获取字段名
        field_name = None
        if '/T' in field_obj:
            field_name = field_obj['/T']
            if hasattr(field_name, 'to_unicode'):
                field_name = field_name.to_unicode()
            elif isinstance(field_name, str):
                field_name = field_name.strip('()')
            else:
                field_name = str(field_name).strip('()')
        
        # 构建字段路径（用于调试）
        current_path = f"{parent_path}.{field_name}" if parent_path and field_name else (field_name or parent_path)
        
        # 获取字段值
        field_value = ""
        if '/V' in field_obj:
            try:
                value = field_obj['/V']
                if hasattr(value, 'to_unicode'):
                    field_value = value.to_unicode()
                elif hasattr(value, 'decode'):
                    field_value = value.decode('utf-8', errors='ignore')
                elif isinstance(value, str):
                    field_value = value.strip('()')
                else:
                    field_value = str(value).strip('()')
            except:
                pass
        
        # 如果有字段名，添加到结果中
        if field_name:
            result_dict[field_name] = {
                'value': field_value,
                'type': field_obj.get('/FT') if '/FT' in field_obj else None,
                'subtype': field_obj.get('/Subtype') if '/Subtype' in field_obj else None,
                'has_options': '/Opt' in field_obj,
                'has_kids': '/Kids' in field_obj and field_obj['/Kids'],
                'options': [],
                'flags': _safe_int_convert(field_obj.get('/Ff')) if '/Ff' in field_obj and field_obj['/Ff'] else None,
                'max_length': _safe_int_convert(field_obj.get('/MaxLen')) if '/MaxLen' in field_obj and field_obj['/MaxLen'] else None,
                'path': current_path  # 添加路径信息用于调试
            }
            
            # 提取选项
            if '/Opt' in field_obj and field_obj['/Opt']:
                try:
                    options = field_obj['/Opt']
                    option_list = []
                    for opt in options:
                        if hasattr(opt, 'to_unicode'):
                            option_list.append(opt.to_unicode())
                        elif isinstance(opt, str):
                            option_list.append(opt.strip('()'))
                        else:
                            option_list.append(str(opt).strip('()'))
                    result_dict[field_name]['options'] = option_list
                except:
                    pass
        
        # 递归处理所有子字段
        if '/Kids' in field_obj and field_obj['/Kids']:
            for kid in field_obj['/Kids']:
                _extract_field_recursive_improved(kid, result_dict, current_path)
                
    except Exception as e:
        # 静默处理单个字段的异常
        pass