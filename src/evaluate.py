import pandas as pd
import joblib
from sklearn.metrics import classification_report, confusion_matrix

model = joblib.load('model.pkl')
X_test = pd.read_csv('data/X_test.csv')
y_test = pd.read_csv('data/y_test.csv').squeeze()

y_pred = model.predict(X_test)

print("=== classification report ===")
print(classification_report(y_test, y_pred))
print("=== confusion matrix ===")
print(confusion_matrix(y_test, y_pred))
print("=== feature importances ===")
importances = sorted(zip(model.feature_importances_, X_test.columns), reverse=True)
for imp, name in importances:
    print(f"{name}: {imp:.4f}")
