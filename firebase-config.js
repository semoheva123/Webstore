// firebase-config.js
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-app.js";
import { 
  getFirestore, 
  collection, 
  addDoc, 
  deleteDoc, 
  doc, 
  onSnapshot 
} from "https://www.gstatic.com/firebasejs/10.8.0/firebase-firestore.js";

// ضع بيانات مشروعك الخاصة من Firebase Console هنا
const firebaseConfig = {
  apiKey: "YOUR_API_KEY",
  authDomain: "efrin-one-store.firebaseapp.com",
  projectId: "efrin-one-store",
  storageBucket: "efrin-one-store.appspot.com",
  messagingSenderId: "YOUR_SENDER_ID",
  appId: "YOUR_APP_ID"
};

// تهيئة Firebase و Firestore
const app = initializeApp(firebaseConfig);
const db = getFirestore(app);

// تصدير الأدوات الأساسية لاستخدامها في الملفات الأخرى
export { db, collection, addDoc, deleteDoc, doc, onSnapshot };
