import os
import json
import time
import logging
from typing import Dict, Any, List, Optional
from backend.app.config import GROQ_API_KEY, GROQ_MODEL

logger = logging.getLogger("gaushala.groq_ai")

class GroqAIAutomationService:
    _instance = None

    def __init__(self):
        self.api_key = GROQ_API_KEY
        self.model = GROQ_MODEL
        self.client = None
        self._init_client()

    def _init_client(self):
        if self.api_key and self.api_key.startswith("gsk_") and len(self.api_key) > 25 and "your_groq_api_key_here" not in self.api_key:
            try:
                from groq import Groq
                self.client = Groq(api_key=self.api_key)
                logger.info(f"Groq AI Client initialized with model {self.model}")
            except Exception as e:
                logger.warning(f"Could not initialize Groq SDK client: {e}")
                self.client = None
        else:
            self.client = None

    def is_groq_active(self) -> bool:
        return self.client is not None

    def diagnose_distress_alert(
        self,
        alert_type: str,
        message: str,
        entity_id: Optional[str] = None,
        duration: Optional[float] = None,
        zone_name: Optional[str] = None,
        symptoms: Optional[List[str]] = None,
        vitals: Optional[Dict[str, Any]] = None,
        lang: str = "en"
    ) -> Dict[str, Any]:
        """
        Generates automated clinical AI veterinary diagnosis & action plan with symptoms & vitals support.
        """
        system_prompt = (
            "You are the Senior Veterinary Medical AI for a Smart Gaushala Cattle Welfare Monitoring Platform. "
            "You provide razor-sharp, actionable clinical guidance for cattle distress triggers, CCTV vision anomalies, and reported physical symptoms. "
            "Respond in structured JSON format with fields: 'assessment', 'risk_score' (1-10), 'immediate_actions' (list of strings), "
            "'medical_protocol' (string), and 'shift_recommendation' (string). "
            f"Provide response in {'Hindi (Devanagari script)' if lang == 'hi' else 'English'}."
        )

        symptoms_str = ", ".join(symptoms) if symptoms else "None specified"
        vitals_str = json.dumps(vitals) if vitals else "Normal parameters"

        user_content = (
            f"Alert Type: {alert_type}\n"
            f"Message: {message}\n"
            f"Cattle ID: #{entity_id or 'Unknown'}\n"
            f"Duration motionless: {int(duration or 0)} seconds\n"
            f"Enclosure: {zone_name or 'Main Shed'}\n"
            f"Clinical Symptoms: {symptoms_str}\n"
            f"Physiological Vitals: {vitals_str}\n"
            "Analyze underlying pathology, differential diagnosis, immediate caretaker first-aid, drug therapy protocol, and shift directive."
        )

        if self.client:
            try:
                chat_completion = self.client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    model=self.model,
                    temperature=0.3,
                    response_format={"type": "json_object"}
                )
                raw_json = chat_completion.choices[0].message.content
                data = json.loads(raw_json)
                data["powered_by"] = f"Groq Cloud AI ({self.model})"
                return data
            except Exception as e:
                logger.error(f"Groq diagnosis generation error: {e}")

        # Intelligent Automated Clinical Fallback when Groq key is pending in .env
        is_hi = (lang == "hi")
        target_name = f"#{entity_id}" if entity_id else ("अज्ञात गोवंश" if is_hi else "monitored cattle")
        pen_name = zone_name or ("निगरानी बाड़ा" if is_hi else "monitored pen")

        # Check symptoms for specialized bovine pathologies
        sym_joined = " ".join(symptoms or []).lower()

        if "bloat" in sym_joined or "tympany" in sym_joined or "आफरा" in sym_joined or "पेट फूलना" in sym_joined:
            return {
                "assessment": (
                    f"गोवंश {target_name} ({pen_name}) में तीव्र आफरा (Rumen Tympany / Bloat) के लक्षण। बाएं कोख (Left paralumbar fossa) का असामान्य उभार, दर्द एवं बेचैनी। किण्वन गैस या झागदार चारे से रुमेन में गैस का संचय।"
                    if is_hi else
                    f"Cattle {target_name} in {pen_name} exhibits acute ruminal tympany (bloat). Severe distension of the left paralumbar fossa, discomfort, and respiratory compression due to entrapment of fermentation gases."
                ),
                "risk_score": 9.2,
                "immediate_actions": [
                    "गोवंश को तुरंत बैठने से रोकें और सिर को थोड़ा ऊंचा रखकर खड़ा रखें" if is_hi else "Keep cattle standing with head elevated; strictly avoid recumbency",
                    "मुंह में लकड़ी की बिट (mouth gag) बांधें ताकि डकार आकर गैस बाहर निकले" if is_hi else "Insert a wooden mouth gag to stimulate salivation and eructation",
                    "पेट के बाएं हिस्से पर तारपीन तेल या सरसों के तेल की हल्की मालिश करें" if is_hi else "Gently massage the left flank; administer 100ml Tympol / Bloatosil drench"
                ],
                "medical_protocol": (
                    "टिम्पोल (Tympol) 100ml अथवा तारपीन का तेल 30-50ml सरसों के तेल में मिलाकर दें। यदि अत्यधिक आपातकाल हो तो ट्रोकार एवं कैन्युला (Trocar & Cannula) द्वारा रुमेन गैस निकालें।"
                    if is_hi else
                    "Administer dimethicone/silicone anti-frothing agent (Bloatosil 100ml) or turpentine oil in mustard oil. In severe asphyxiation distress, perform emergency trocarization of left flank."
                ),
                "shift_recommendation": (
                    "बाड़े में उपलब्ध गीला या फंगसयुक्त चारा तुरंत हटा दें तथा अगले 12 घंटे तक सूखा भूसा ही दें।"
                    if is_hi else
                    "Immediately withdraw lush/fermented legume fodder from trough; provide dry straw for next 12 hours."
                ),
                "powered_by": "Automated Veterinary Rules Engine (Add GROQ_API_KEY in .env for live Groq LLaMA-3.3 acceleration)"
            }
        elif "nodule" in sym_joined or "lump" in sym_joined or "गांठ" in sym_joined or "lumpy" in sym_joined:
            return {
                "assessment": (
                    f"गोवंश {target_name} ({pen_name}) की त्वचा पर गांठें एवं तेज बुखार। लंपी स्किन रोग (Lumpy Skin Disease - Capripoxvirus) का प्रबल संदेह। यह रोग मच्छरों एवं मक्खियों द्वारा फैलता है।"
                    if is_hi else
                    f"Cattle {target_name} in {pen_name} shows cutaneous skin nodules and pyrexia, strongly indicative of Lumpy Skin Disease (LSD). High transmission vector via biting flies and ticks."
                ),
                "risk_score": 8.8,
                "immediate_actions": [
                    "संक्रमित गोवंश को तुरंत स्वस्थ झुंड से अलग क्वारंटाइन शेड में शिफ्ट करें" if is_hi else "Immediately isolate infected cattle into the quarantine ward",
                    "शेड में नीम की पत्तियों का धुआं करें एवं कीटनाशक स्प्रे (Deltamethrin) का छिड़काव करें" if is_hi else "Perform vector fogging (neem smoke / deltamethrin spray) to eliminate flies",
                    "घाव एवं गांठों पर एंटीसेप्टिक स्प्रे (Topicure/Betadine) का प्रयोग करें" if is_hi else "Spray topical wound healing aerosol (Topicure/Betadine) on ruptured skin nodules"
                ],
                "medical_protocol": (
                    "पेरासिटामोल/मेलोक्सीकैम बुखार एवं दर्द हेतु, एंटीहिस्टामिनिक (Pheniramine maleate), तथा द्वितीयक जीवाणु संक्रमण रोकने हेतु एंटीबायोटिक (Enrofloxacin) पशु चिकित्सक के निर्देशानुसार दें।"
                    if is_hi else
                    "Administer NSAID (Meloxicam 0.5mg/kg), antihistamine (Avil 10ml), and secondary antibiotic cover (Enrofloxacin/Oxytetracycline) under veterinary prescription."
                ),
                "shift_recommendation": (
                    "पूरे बाड़े के अन्य सभी गोवंशों का गोट पॉक्स टीकाकरण रिकॉर्ड जांचें एवं क्वारंटाइन लॉक लगाएं।"
                    if is_hi else
                    "Audit Goat Pox vaccine compliance across entire herd; impose strict biosecurity quarantine."
                ),
                "powered_by": "Automated Veterinary Rules Engine (Add GROQ_API_KEY in .env for live Groq LLaMA-3.3 acceleration)"
            }
        elif "salivation" in sym_joined or "लार" in sym_joined or "drool" in sym_joined or "fmd" in sym_joined or "खुर" in sym_joined:
            return {
                "assessment": (
                    f"गोवंश {target_name} ({pen_name}) में मुंह से तारदार लार गिरना, लंगड़ाना एवं खुरों में छाले। खुरपका-मुंहपका रोग (Foot-and-Mouth Disease - Aphthovirus) के स्पष्ट नैदानिक लक्षण।"
                    if is_hi else
                    f"Cattle {target_name} in {pen_name} demonstrates ropy hypersalivation, lameness, and foot/mouth vesicles. Pathognomonic indicators of Foot-and-Mouth Disease (FMD)."
                ),
                "risk_score": 9.0,
                "immediate_actions": [
                    "बाड़े के मुख्य द्वार पर पोटेशियम परमैंगनेट (लाल दवा) का फुट-बाथ (Foot-bath) तैयार करें" if is_hi else "Establish a 1:1000 Potassium Permanganate foot-bath barrier at pen entrance",
                    "मुंह के छालों को बोरिक एसिड ग्लिसरीन घोल अथवा फिटकरी पानी से धोएं" if is_hi else "Gently wash oral lesions with alum solution (2%) or boro-glycerine",
                    "मुलायम एवं पतला दलिया या हरा चारा ही खाने को दें" if is_hi else "Provide soft drenching porridge / crushed green forage due to sore mouth"
                ],
                "medical_protocol": (
                    "खुरों के घावों पर पोटाश वाश के बाद टॉपिक्योर स्प्रे लगाएं। दर्द निवारक (Flunixin Meglumine) तथा जटिलताओं से बचाव हेतु एंटीबायोटिक का उपयोग करें।"
                    if is_hi else
                    "Wash hooves with KMnO4 solution, apply fly-repellent wound spray, administer analgesic (Flunixin/Meloxicam) and broad-spectrum antibiotic."
                ),
                "shift_recommendation": (
                    "गौशाला के मुख्य प्रवेश पर बाहरी वाहनों एवं व्यक्तियों की आवाजाही पर पूर्ण प्रतिबंध लगाएं।"
                    if is_hi else
                    "Impose zero-tolerance quarantine lock; notify regional government veterinary dispensary."
                ),
                "powered_by": "Automated Veterinary Rules Engine (Add GROQ_API_KEY in .env for live Groq LLaMA-3.3 acceleration)"
            }
        elif "fever" in sym_joined or "बुखार" in sym_joined or "temp" in sym_joined:
            return {
                "assessment": (
                    f"गोवंश {target_name} ({pen_name}) में उच्च शारीरिक तापमान (>103.5°F), सुस्ती एवं चारा बंद होना। संभावित सिस्टेमिक संक्रमण अथवा टिक-जनित प्रोटोजोआ (Theileriosis/Babesiosis)।"
                    if is_hi else
                    f"Cattle {target_name} in {pen_name} shows pyrexia (>103.5°F), anorexia, and lethargy. High suspicion of systemic bacterial infection or tick-borne hemoprotozoan disease (Theileria/Babesia)."
                ),
                "risk_score": 8.0,
                "immediate_actions": [
                    "गोवंश के सिर और गर्दन पर ठंडा पानी डालकर तापमान नियंत्रित करें" if is_hi else "Apply cool water hydrotherapy to head and poll to counter thermal shock",
                    "शरीर पर चिचड़ी/जूँ (ticks) की उपस्थिति की सूक्ष्म जांच करें" if is_hi else "Inspect perineum, ears, and dewlap for engorged tick vectors",
                    "ताजा इलेक्ट्रोलाइट जल उपलब्ध कराएं" if is_hi else "Provide ad-libitum oral electrolyte rehydration solution"
                ],
                "medical_protocol": (
                    "मेलोक्सीकैम + पेरासिटामोल इंजेक्शन (Melonex Plus 15-20ml I/M), रक्त की जांच (Blood Smear) करवाकर एंटी-प्रोटोजोअल या एंटीबायोटिक दें।"
                    if is_hi else
                    "Administer Meloxicam + Paracetamol (Melonex Plus 20ml I/M). Draw peripheral blood smear for protozoa smear testing."
                ),
                "shift_recommendation": (
                    "प्रत्येक 3 घंटे पर रेक्टल तापमान की पुनः जांच दर्ज करें।"
                    if is_hi else
                    "Log rectal temperature every 3 hours until normothermia (<102°F) is restored."
                ),
                "powered_by": "Automated Veterinary Rules Engine (Add GROQ_API_KEY in .env for live Groq LLaMA-3.3 acceleration)"
            }

        if alert_type == "PROSTRATION_DISTRESS":
            return {
                "assessment": (
                    f"गोवंश {target_name} ({pen_name}) पिछले {int(duration or 60)} सेकंड से असामान्य रूप से स्थिर है। संभवतः तीव्र पेट दर्द (Colic), हाइपोकैल्सीमिया (Milk Fever), अथवा अत्यधिक गर्मी/थकान के लक्षण।"
                    if is_hi else
                    f"Cattle {target_name} in {pen_name} has remained motionless for {int(duration or 60)}s. Indicates high risk of sternal/lateral recumbency distress, hypocalcemia (milk fever), or acute heat stress."
                ),
                "risk_score": 8.5,
                "immediate_actions": [
                    "तुरंत शेड परिचारक को गोवंश के पास शारीरिक जांच हेतु भेजें" if is_hi else "Dispatch enclosure caretaker immediately for physical vital check",
                    "श्वास दर (Respiration Rate) एवं आंख की पुतलियों की प्रतिक्रिया जांचें" if is_hi else "Inspect pupillary reflex, respiration rate, and rectal temperature",
                    "गोवंश को हल्के से खड़ा करने का प्रयास करें, यदि खड़ा न हो तो अलग चिकित्सा वार्ड में शिफ्ट करें" if is_hi else "Gently attempt to make cattle stand; if unable to rise, transfer to medical quarantine"
                ],
                "medical_protocol": (
                    "इलेक्ट्रोलाइट घोल, गुनगुना पानी तथा आवश्यकतानुसार कैल्शियम बोरो-ग्लूकोनेट (CBG) इंजेक्शन पशु चिकित्सक के परामर्श से तैयार रखें।"
                    if is_hi else
                    "Prepare electrolyte hydration, warm water drenching, and hold Calcium Borogluconate (CBG) under veterinary supervision."
                ),
                "shift_recommendation": (
                    f"अगले 2 घंटे तक {pen_name} पर लगातार वीडियो एवं प्रत्यक्ष निगरानी रखें।"
                    if is_hi else
                    f"Maintain continuous 15-minute observational loop on {pen_name}."
                ),
                "powered_by": "Automated Veterinary Rules Engine (Add GROQ_API_KEY in .env for live Groq LLaMA-3.3 acceleration)"
            }
        elif alert_type == "GEOFENCE_BREACH":
            return {
                "assessment": (
                    f"गोवंश {target_name} द्वारा {pen_name} की परिधि का उल्लंघन दर्ज किया गया है। बाउंड्री गेट में ढीलापन या गोवंश में घबराहट की संभावना।"
                    if is_hi else
                    f"Cattle {target_name} crossed the {pen_name} safety perimeter geofence. Potential boundary latch failure, panic trigger, or feed attraction outside pen."
                ),
                "risk_score": 7.0,
                "immediate_actions": [
                    "परिधि गेट एवं बाउंड्री तारों की त्वरित जांच" if is_hi else "Immediate security inspection of perimeter gates and fencing",
                    "गोवंश को शांत वातावरण में सुरक्षित बाड़े में वापस लाएं" if is_hi else "Calmly guide the cattle back into designated pen bay",
                    "अन्य गोवंश के पीछे जाने से रोकने हेतु द्वितीयक बैरियर बंद करें" if is_hi else "Engage secondary geofence barrier to prevent herd scatter"
                ],
                "medical_protocol": (
                    "खरोंच अथवा चोट की जांच करें और एंटीसेप्टिक स्प्रे (Betadine/Topicure) लगाएं।"
                    if is_hi else
                    "Inspect legs and flank for abrasive lacerations; apply topical antiseptic if required."
                ),
                "shift_recommendation": (
                    "शेड सुरक्षा गार्ड को बाड़ा परिधि का वॉकथ्रू करने का निर्देश दें।"
                    if is_hi else
                    "Schedule immediate physical perimeter walkthrough for on-duty caretaker."
                ),
                "powered_by": "Automated Veterinary Rules Engine (Add GROQ_API_KEY in .env for live Groq LLaMA-3.3 acceleration)"
            }
        else:
            return {
                "assessment": (
                    "चारागाह पर निर्धारित क्षमता से अधिक गोवंश एकत्र होने से प्रतिस्पर्धा एवं चोट का खतरा।"
                    if is_hi else
                    "Trough crowding density exceeded threshold, posing risk of horn collision and competitive feeding distress."
                ),
                "risk_score": 5.5,
                "immediate_actions": [
                    "पूरक चारागाह गर्त (Secondary Feeder) में हरा चारा वितरित करें" if is_hi else "Disperse feed evenly across secondary feeder trough bays",
                    "कमजोर या वृद्ध गोवंश को सुरक्षित दूरी पर अलग से चारा उपलब्ध कराएं" if is_hi else "Ensure weaker or submissive cattle are provided separate feeding space"
                ],
                "medical_protocol": (
                    "पर्याप्त स्वच्छ पेयजल की उपलब्धता सुनिश्चित करें।"
                    if is_hi else
                    "Ensure adequate freshwater supply in adjacent watering bays."
                ),
                "shift_recommendation": (
                    "चारागाह समय सारिणी को दो चरणों में विभाजित करें।"
                    if is_hi else
                    "Stagger feeding schedule into phased morning/evening intervals."
                ),
                "powered_by": "Automated Veterinary Rules Engine (Add GROQ_API_KEY in .env for live Groq LLaMA-3.3 acceleration)"
            }

    def generate_shift_audit_report(self, metrics: Optional[Dict[str, Any]] = None, lang: str = "en", shift_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Generates an automated executive AI shift audit report.
        """
        shift_label = shift_name or "Current Duty Shift"
        if not metrics:
            try:
                from backend.app.camera.stream_manager import get_stream_manager
                metrics = get_stream_manager().get_system_metrics()
            except Exception:
                metrics = {}

        total = metrics.get("total_cattle", 0)
        active = metrics.get("active_cattle", 0)
        resting = metrics.get("resting_cattle", 0)
        cams_online = metrics.get("cameras_online", 0)
        cams_total = metrics.get("cameras_total", 4)
        is_hi = (lang == "hi")

        try:
            from backend.app.alerts.alert_engine import get_alert_engine
            alerts_list = get_alert_engine().get_alerts()
            alerts_logged = len(alerts_list)
        except Exception:
            alerts_logged = 0

        user_content = (
            f"Generate a Gaushala Veterinary Shift Audit Report.\n"
            f"Metrics: Total Cattle: {total}, Active: {active}, Resting: {resting}, Surveillance Cameras Online: {cams_online}/{cams_total}, Logged Alerts: {alerts_logged}.\n"
            f"Language: {'Hindi' if is_hi else 'English'}."
        )

        if self.client:
            try:
                system_prompt = (
                    "You are the Executive Veterinary Officer of the National Gaushala Surveillance Mission. "
                    "Write an authoritative 3-paragraph executive shift audit report covering: "
                    "1. Herd Census & Vital Ratio 2. Pen Inactivity & Perimeter Compliance 3. Action Items for Next Shift."
                )
                chat_completion = self.client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    model=self.model,
                    temperature=0.4,
                    max_tokens=600
                )
                markdown = chat_completion.choices[0].message.content
                return {
                    "title": "गौशाला ए.आई. शिफ्ट ऑडिट रिपोर्ट" if is_hi else "Gaushala AI Shift Audit Report",
                    "report_markdown": markdown,
                    "key_clinical_findings": [
                        f"YOLOv8 optical census: {total} cattle tracked across operational camera feeds",
                        f"Activity ratio: {active} active, {resting} resting within expected rumination curve",
                        f"Surveillance status: {cams_online}/{cams_total} camera nodes online, {alerts_logged} active alerts logged"
                    ],
                    "supervisor_tasks": [
                        "Complete physical vital sign check on quarantined or motionless cattle",
                        "Ensure continuous freshwater refilling at all trough stations",
                        "Log evening feed intake and confirm barn lighting for night shift"
                    ],
                    "herd_census": {
                        "total_headcount": total,
                        "motion_nominal_percent": f"{int((active/max(1, total))*100)}%" if total > 0 else "0%",
                        "alerts_logged": alerts_logged
                    },
                    "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "shift": shift_label,
                    "model": self.model,
                    "powered_by": f"Groq Cloud AI ({self.model})"
                }
            except Exception as e:
                logger.error(f"Groq shift report error: {e}")

        # Intelligent Structured Fallback Report using live telemetry
        if is_hi:
            report_title = "गौशाला ए.आई. शिफ्ट ऑडिट रिपोर्ट"
            findings = [
                f"वास्तविक समय YOLOv8 विज़न गणना: कुल {total} गोवंश ट्रैक किए गए ({active} सक्रिय, {resting} विश्रामरत)।",
                f"सीसीटीवी नोड्स: {cams_online}/{cams_total} नोड्स सक्रिय। कुल दर्ज अलर्ट: {alerts_logged}।",
                "कैमरा विज़न आधारित व्यवहार एवं परिधि सुरक्षा निरंतर सक्रिय।"
            ]
            tasks = [
                "सक्रिय अलर्ट रजिस्टर की समीक्षा करें और आवश्यक निवारण कदम उठाएं।",
                "पानी के गर्तों में ताज़ा जल आपूर्ति स्तर 80% से ऊपर बनाए रखें।",
                "शाम की ड्यूटी शिफ्ट हेतु चारे का समान वितरण सुनिश्चित करें।"
            ]
        else:
            report_title = "Gaushala AI Veterinary Shift Audit Report"
            findings = [
                f"Real-time YOLOv8 optical census tracks {total} total head ({active} active, {resting} resting).",
                f"Surveillance node availability: {cams_online}/{cams_total} online with {alerts_logged} logged alerts.",
                "Automated behavioral analytics and boundary geofences actively monitoring."
            ]
            tasks = [
                "Inspect any active alerts logged in the Alert Registry.",
                "Maintain clean fresh water supply at all drinking trough stations above 80%.",
                "Replenish mineral salt licks and confirm feed availability."
            ]

        return {
            "title": report_title,
            "key_clinical_findings": findings,
            "supervisor_tasks": tasks,
            "herd_census": {
                "total_headcount": total,
                "motion_nominal_percent": f"{int((active/max(1, total))*100)}%" if total > 0 else "0%",
                "alerts_logged": alerts_logged
            },
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "shift": shift_label,
            "model": "Hybrid Clinical Rules Engine (Groq ready in .env)",
            "powered_by": "Gaushala AI Automation Engine"
        }

    def ask_ai_assistant(self, question: str, context: Optional[str] = None, lang: str = "en") -> Dict[str, Any]:
        """
        Interactive Veterinary AI assistant.
        """
        is_hi = (lang == "hi")
        if self.client:
            try:
                system_prompt = (
                    "You are the expert Veterinary Cattle AI Consultant for the Smart Gaushala CCTV Platform. "
                    "Provide authoritative, concise, and scientifically accurate livestock health, shed management, "
                    "and automated alert troubleshooting advice. "
                    f"Respond in {'Hindi' if is_hi else 'English'}."
                )
                user_msg = f"Context: {context or 'None'}\nQuestion: {question}"
                chat_completion = self.client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_msg}
                    ],
                    model=self.model,
                    temperature=0.3,
                    max_tokens=450
                )
                return {
                    "answer": chat_completion.choices[0].message.content,
                    "model": self.model,
                    "powered_by": f"Groq Cloud ({self.model})"
                }
            except Exception as e:
                logger.error(f"Groq chat error: {e}")

        # Intelligent Fallback
        q_lower = question.lower()
        if "prostrat" in q_lower or "distress" in q_lower or "recumben" in q_lower or "बीमार" in question or "बैठ" in question:
            ans = (
                "गोवंश यदि 15-20 मिनट से अधिक बिना हिले-डुले लेटा रहे, तो यह हाइपोकैल्सीमिया (Milk Fever), आफरा (Tympanites/Bloat), अथवा पेट दर्द का संकेत हो सकता है। "
                "तुरंत परिचारक को भेजकर श्वास दर (सामान्य: 15-30/मिनट), पेट का फूलना, एवं आंख की चमक जांचें। यदि आवश्यक हो तो पशु चिकित्सक को तुरंत सूचित करें।"
                if is_hi else
                "Prolonged motionless recumbency beyond 15-20 minutes is a classic clinical indicator of hypocalcemia (milk fever), rumen tympany/bloat, or acute colic distress. "
                "Immediate steps: 1. Approach quietly and check if the cow can rise with mild stimulation. 2. Auscultate rumen motility. 3. Check for cool ears (sign of hypocalcemia). Call the veterinarian if recumbency continues."
            )
        elif "feed" in q_lower or "चारा" in question:
            ans = (
                "चारागाह में प्रति वयस्क गोवंश न्यूनतम 2.5 से 3 फीट गर्त (feeder space) होना चाहिए। अत्यधिक भीड़ से बचने हेतु चारे को दो अलग-अलग गर्तों में बराबर बांटें एवं स्वच्छ जल की निर्बाध आपूर्ति रखें।"
                if is_hi else
                "Each adult dairy cow requires approximately 2.5 to 3 linear feet of bunk space. To eliminate feeder trough bottlenecks, distribute dry fodder and fresh green forage simultaneously across two distinct trough stations."
            )
        else:
            ans = (
                f"आपके प्रश्न '{question}' के संदर्भ में: स्मार्ट गौशाला ए.आई. प्रणाली 24x7 सीसीटीवी विज़न, वजन एवं गतिशीलता पर नज़र रखती है। किसी भी असामान्यता के लिए अलर्ट टैब की समीक्षा करें अथवा .env में GROQ_API_KEY दर्ज कर लाइव LLaMA-3.3 से गहन सलाह प्राप्त करें।"
                if is_hi else
                f"Regarding your query '{question}': The Smart Gaushala system continuously tracks herd posture, feeder occupancy, and perimeter containment. Check the AI Alerts tab for active anomalies, or add your GROQ_API_KEY in .env for live Groq ultra-low-latency veterinary reasoning."
            )

        return {
            "answer": ans,
            "model": "Clinical Rules Engine (Groq ready in .env)",
            "powered_by": "Gaushala AI Automation Engine"
        }

_global_groq_service = None

def get_groq_service() -> GroqAIAutomationService:
    global _global_groq_service
    if _global_groq_service is None:
        _global_groq_service = GroqAIAutomationService()
    return _global_groq_service
