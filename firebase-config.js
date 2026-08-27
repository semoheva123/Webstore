// firebase-config.js
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-app.js";
import { getAnalytics } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-analytics.js";
import { 
  getFirestore, collection, addDoc, deleteDoc, doc, updateDoc, onSnapshot, getDoc, setDoc 
} from "https://www.gstatic.com/firebasejs/10.8.0/firebase-firestore.js";
import { 
  getAuth, createUserWithEmailAndPassword, signInWithEmailAndPassword, signOut, onAuthStateChanged 
} from "https://www.gstatic.com/firebasejs/10.8.0/firebase-auth.js";

const firebaseConfig = {
  apiKey: "AIzaSyBObnUf_n6dcpQEiNkE0Wcn8et_Fmn9jDY",
  authDomain: "store-afbeb.firebaseapp.com",
  projectId: "store-afbeb",
  storageBucket: "store-afbeb.firebasestorage.app",
  messagingSenderId: "727224850533",
  appId: "1:727224850533:web:1b9c776e402bfc1d474e8c",
  measurementId: "G-KVNDNVWYK3"
};

const app = initializeApp(firebaseConfig);
const analytics = getAnalytics(app);
const db = getFirestore(app);
const auth = getAuth(app);

export { 
  db, auth, analytics, collection, addDoc, deleteDoc, doc, updateDoc, onSnapshot, getDoc, setDoc,
  createUserWithEmailAndPassword, signInWithEmailAndPassword, signOut, onAuthStateChanged 
};
