import { initializeApp } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-app.js";
import { getAnalytics } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-analytics.js";
import { 
  getFirestore, collection, addDoc, deleteDoc, doc, updateDoc, onSnapshot, getDoc, setDoc 
} from "https://www.gstatic.com/firebasejs/10.8.0/firebase-firestore.js";
import { 
  getAuth, createUserWithEmailAndPassword, signInWithEmailAndPassword, signOut, onAuthStateChanged 
} from "https://www.gstatic.com/firebasejs/10.8.0/firebase-auth.js";

const firebaseConfig = {
  apiKey: "AIzaSyDACjoZ3pw1nnlPKrPpEaHprwKbhJdlu9U",
  authDomain: "webstore-a6ca3.firebaseapp.com",
  projectId: "webstore-a6ca3",
  storageBucket: "webstore-a6ca3.firebasestorage.app",
  messagingSenderId: "259371594335",
  appId: "1:259371594335:web:b86a02409f740b892f61ea",
  measurementId: "G-D1SJRKYPJH"
};

const app = initializeApp(firebaseConfig);
const analytics = getAnalytics(app);
const db = getFirestore(app);
const auth = getAuth(app);

export { 
  db, auth, analytics, collection, addDoc, deleteDoc, doc, updateDoc, onSnapshot, getDoc, setDoc,
  createUserWithEmailAndPassword, signInWithEmailAndPassword, signOut, onAuthStateChanged 
};
